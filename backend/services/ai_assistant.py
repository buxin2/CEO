"""Groq-powered management agent with tool calling."""

import json
import re
import uuid
from datetime import date

from models import get_week_bounds
from services.ai_tools import TOOL_DEFINITIONS, execute_tool_call
from services.app_knowledge import build_ai_app_knowledge_text
from services.owner_profile_service import build_ai_owner_profile_text, resolve_owner_display_name
from services.groq_key_service import get_active_groq_config, mark_key_used

_KNOWN_TOOL_NAMES = {t["function"]["name"] for t in TOOL_DEFINITIONS}

_READ_ONLY_TOOL_NAMES = {
    "list_companies",
    "get_company",
    "list_employees",
    "list_tasks",
    "get_dashboard_summary",
    "get_pending_work",
    "list_products",
    "list_services",
    "get_earnings_summary",
    "get_planner_snapshot",
    "list_timetable",
}

_READ_ONLY_TOOL_DEFINITIONS = [
    t for t in TOOL_DEFINITIONS
    if t.get("function", {}).get("name") in _READ_ONLY_TOOL_NAMES
]

_WRITE_TOOL_NAMES = {
    "create_company",
    "update_company",
    "delete_company",
    "create_employee",
    "update_employee",
    "delete_employee",
    "create_tasks",
    "update_task",
    "delete_task",
    "create_product",
    "update_product",
    "delete_product",
    "create_service",
    "update_service",
    "delete_service",
    "create_earning",
    "delete_earning",
    "create_timetable_item",
    "update_timetable_item",
    "delete_timetable_item",
    "reset_timetable",
    "generate_timetable",
    "create_planner_goal",
    "update_planner_notes",
}

_FAILED_GEN_PATTERNS = [
    re.compile(r"<function=(\w+)=(\{.*?\})(?:\s*/?>|</function>|$)", re.DOTALL),
    re.compile(r"<function=(\w+)\s*(\{.*?\})(?:\s*/?>|</function>|$)", re.DOTALL),
    re.compile(r"<function=(\w+),\s*(\{.*?\})", re.DOTALL),
]

_GREETING_RE = re.compile(
    r"^(hi|hello|hey|yo|good\s+(morning|afternoon|evening)|thanks|thank\s+you|ok|okay)[\s!.?]*$",
    re.I,
)

_ACTION_WORDS = (
    "create", "add", "delete", "remove", "assign", "update", "build", "make", "set up", "setup",
    "timetable", "schedule", "planner", "generate",
)

_TIMETABLE_COMMAND_RE = re.compile(
    r"(?:"
    r"\b(create|generate|build|make|add|set up|setup|plan)\b.{0,40}\b(time\s*table|timetable|schedule|planner|my\s+day|daily\s+plan)"
    r"|"
    r"\b(time\s*table|timetable|schedule|planner)\b.{0,20}\b(for me|please|now|today|tomorrow)"
    r"|"
    r"\b(generate|reset)\s+(?:my\s+)?(?:timetable|time\s*table|schedule|planner)"
    r")",
    re.I,
)

# Explicit management commands — casual mention of "company" in life talk must NOT match.
_MANAGEMENT_COMMAND_RE = re.compile(
    r"(?:"
    r"\b(create|add|make|set up|setup|build|generate)\s+(?:a\s+|the\s+|my\s+|new\s+)*"
    r"(company|companies|employee|employees|task|tasks|product|products|service|services|earning|earnings|"
    r"timetable|time\s*table|schedule|planner)"
    r"|"
    r"\b(delete|remove)\s+(?:a\s+|the\s+|my\s+)*"
    r"(company|companies|employee|employees|task|tasks|product|products|service|services|earning|earnings)"
    r"|"
    r"\b(list|show|get|display)\s+(?:all\s+|my\s+|the\s+)*"
    r"(companies|company|employees|employee|tasks|task|products|product|services|service|earnings)"
    r"|"
    r"\b(assign|give)\s+.+\s+tasks?"
    r"|"
    r"\b(update|edit|change)\s+(?:a\s+|the\s+|my\s+)*"
    r"(company|companies|employee|employees|task|tasks|product|products|service|services|timetable|schedule)"
    r"|"
    r"\b(generate|reset)\s+(?:my\s+)?(?:timetable|time\s*table|schedule|planner)"
    r"|"
    r"\b(what|which)\s+companies\b"
    r"|"
    r"\bwho\s+(?:works|is)\s+(?:at|on|in)\b"
    r")",
    re.I,
)

_CHAT_NEGATION_RE = re.compile(
    r"\b(don'?t|do not|no need to|you don'?t have to|not asking you to)\s+"
    r"(create|add|make|do|change|delete|anything)",
    re.I,
)

_CHAT_PERSONAL_RE = re.compile(
    r"\b(my life|talk about my|as a friend|you are my friend|personal|university|college|"
    r"family|feelings|advice|mentor|how am i|how my life|just talking|just chat)\b",
    re.I,
)

_HISTORY_ERROR_PREFIX = "I couldn't complete that request:"
_MAX_PRIOR_MESSAGES = 2
_MAX_PRIOR_MESSAGE_CHARS = 2000


class _FunctionStub:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCallStub:
    def __init__(self, tool_id, name, arguments):
        self.id = tool_id
        self.function = _FunctionStub(name, arguments)


def _split_mangled_tool_name(name):
    """Groq Llama models sometimes embed JSON in function.name."""
    if not name or not isinstance(name, str):
        return name, None
    name = name.strip()
    if "=" in name:
        tool_name, rest = name.split("=", 1)
        rest = rest.strip()
        if rest.startswith("{") or rest.startswith("["):
            return tool_name.strip(), rest
    if "," in name:
        tool_name, rest = name.split(",", 1)
        rest = rest.strip()
        if rest.startswith("{") or rest.startswith("["):
            return tool_name.strip(), rest
    return name, None


def _normalize_tool_call(name, arguments):
    args = arguments if arguments is not None else ""
    if isinstance(args, str) and args.strip() in ("", "{}"):
        fixed_name, recovered = _split_mangled_tool_name(name)
        if recovered:
            return fixed_name, recovered
    if not isinstance(args, str):
        args = json.dumps(args)
    return (name or "").strip(), args.strip() or "{}"


def _parse_failed_generation(text):
    if not text:
        return None, None
    for pattern in _FAILED_GEN_PATTERNS:
        match = pattern.search(text.strip())
        if match:
            return match.group(1), match.group(2)
    return None, None


def _extract_failed_generation(exc):
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return body.get("error", {}).get("failed_generation")
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            data = response.json()
            return data.get("error", {}).get("failed_generation")
        except Exception:
            pass
    text = str(exc)
    if "failed_generation" in text:
        match = re.search(r"'failed_generation':\s*'([^']+)'", text)
        if match:
            return match.group(1)
    return None


def _is_tool_use_failed(exc):
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return body.get("error", {}).get("code") == "tool_use_failed"
    return "tool_use_failed" in str(exc)


def _is_rate_limit_error(exc):
    text = str(exc).lower()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        code = body.get("error", {}).get("code", "")
        if code == "rate_limit_exceeded":
            return True
    return "rate_limit" in text or "rate limit" in text or "error code: 429" in text or "error code: 413" in text


def _friendly_api_error(exc):
    if _is_rate_limit_error(exc):
        return (
            "Groq API rate limit reached. Wait a few minutes or switch to another saved Groq API key. "
            "Use Clear conversation to avoid sending long old messages."
        )
    return str(exc)


def _last_user_message(messages):
    for item in reversed(messages):
        if item.get("role") == "user":
            return (item.get("content") or "").strip()
    return ""


def _is_small_talk(text):
    t = (text or "").strip()
    if not t:
        return True
    if _GREETING_RE.match(t):
        return True
    if _MANAGEMENT_COMMAND_RE.search(t):
        return False
    lower = t.lower()
    if len(t) < 48 and len(t.split()) <= 4:
        return not any(word in lower for word in _ACTION_WORDS)
    return False


def _is_timetable_request(text):
    t = (text or "").strip()
    if not t:
        return False
    return bool(_TIMETABLE_COMMAND_RE.search(t))


def _user_wants_management_action(text):
    """True only for explicit app management commands, not casual conversation."""
    t = (text or "").strip()
    if not t or _is_small_talk(t):
        return False
    if _TIMETABLE_COMMAND_RE.search(t):
        return True
    if _CHAT_NEGATION_RE.search(t):
        return False
    if _CHAT_PERSONAL_RE.search(t) and not _MANAGEMENT_COMMAND_RE.search(t):
        return False
    if _MANAGEMENT_COMMAND_RE.search(t):
        return True
    lower = t.lower()
    if re.match(r"^\s*(create|add|delete|remove|list|show|assign|update|generate|build|make)\s+", lower):
        return True
    if re.search(r"\b(create|generate|build|make)\b", lower) and re.search(
        r"\b(timetable|time\s*table|schedule|planner)\b", lower
    ):
        return True
    return False


def _parse_timetable_plan_date(text, default=None):
    """Infer today/tomorrow from user message."""
    ref = default or date.today()
    lower = (text or "").lower()
    if "tomorrow" in lower:
        from datetime import timedelta

        return ref + timedelta(days=1)
    if "next week" in lower:
        from datetime import timedelta

        return ref + timedelta(days=7)
    return ref


def _run_timetable_generate_reply(user_text, admin_id=None):
    """Direct timetable generation — avoids flaky tool-calling for common requests."""
    from services.planner_ai import generate_timetable_with_ai
    from services.planner_service import list_timetable_for_date, serialize_item, timetable_progress

    plan_date = _parse_timetable_plan_date(user_text)
    lower = (user_text or "").lower()
    replace = any(w in lower for w in ("replace", "new schedule", "fresh", "regenerate", "redo"))

    result = generate_timetable_with_ai(
        plan_date,
        replace_existing=replace,
        extra_instructions=user_text,
    )
    items = list_timetable_for_date(plan_date)
    prog = timetable_progress(items)
    focus = result.get("today_focus") or []
    focus_txt = ""
    if focus:
        focus_txt = "Today's focus: " + "; ".join(focus[:3]) + "\n\n"

    lines = [f"Done — I created your timetable for **{plan_date.isoformat()}**.\n"]
    lines.append(focus_txt)
    lines.append(f"**{prog['total']} activities** scheduled ({prog['completed']} completed so far).\n")
    preview = items[:8]
    if preview:
        lines.append("Preview:")
        for item in preview:
            lines.append(f"• {item.start_time}–{item.end_time}: {item.title}")
        if len(items) > len(preview):
            lines.append(f"… and {len(items) - len(preview)} more.")
    lines.append("\nOpen **My Timetable** to view, edit, or mark items complete.")
    return "\n".join(lines)


def _user_wants_action(text):
    """Alias used by tool-guard paths."""
    return _user_wants_management_action(text)


def _shorten_text(text, max_len):
    t = (text or "").strip()
    if not max_len or len(t) <= max_len:
        return t
    return t[:max_len].rstrip() + "…"


def _compress_messages_for_api(messages, mode):
    """
    Send the current message (full length) plus the last 2 chat lines for continuity.
    Clear chat resets history so the AI starts fresh when the user chooses.
    """
    if not messages:
        return messages

    prior = list(messages[:-1])
    current = messages[-1]

    if len(prior) > _MAX_PRIOR_MESSAGES:
        prior = prior[-_MAX_PRIOR_MESSAGES:]

    compressed = []
    for item in prior:
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _shorten_text(item.get("content"), _MAX_PRIOR_MESSAGE_CHARS)
        if content:
            compressed.append({"role": role, "content": content})

    role = current.get("role") or "user"
    content = (current.get("content") or "").strip()
    compressed.append({"role": role, "content": content})
    return compressed


def sanitize_chat_history(history):
    """Keep only the last 2 messages for API context (full up to prior char cap)."""
    cleaned = []
    for item in history:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if content.startswith(_HISTORY_ERROR_PREFIX):
            continue
        cleaned.append({
            "role": role,
            "content": _shorten_text(content, _MAX_PRIOR_MESSAGE_CHARS),
        })

    if len(cleaned) > _MAX_PRIOR_MESSAGES:
        cleaned = cleaned[-_MAX_PRIOR_MESSAGES:]

    return cleaned


def _build_system_prompt(context, week_start, week_end, mode="chat", admin_id=None):
    last_co = context.get("last_company_name") or "none"
    last_emp = context.get("last_employee_name") or "none"
    today = date.today().isoformat()
    owner_profile = build_ai_owner_profile_text(admin_id)
    app_knowledge = build_ai_app_knowledge_text()
    user_name = resolve_owner_display_name(admin_id)

    if mode == "chat":
        return (
            f"You are {user_name}'s personal AI mentor and strategic advisor inside their management dashboard.\n\n"
            f"Today: {today}\n\n"
            f"{owner_profile}\n\n"
            "LIVE APP DATABASE (refreshed every message — your source of truth for business facts):\n"
            f"{app_knowledge}\n\n"
            f"Recent AI context: last company in Manage actions: {last_co}; last employee: {last_emp}.\n\n"
            "CHAT MODE (advise and mentor — do not change the app):\n"
            "- You ALREADY know this person and every company, employee name, role, product, service, earnings, "
            "and task progress listed above. Use it confidently.\n"
            "- NEVER say you cannot see products, services, or employees. NEVER say data is unavailable.\n"
            "- When asked to list companies or employees, answer from the LIVE APP DATABASE with names.\n"
            "- Give practical advice on making money, priorities, and who is performing well or needs help.\n"
            "- Continue the conversation naturally (you also receive the last couple of chat messages).\n"
            "- You cannot create, update, or delete app data in this mode.\n"
            "- For app changes, tell the user to switch to **Manage** mode and state a clear command.\n"
        )

    base = (
        f"You are {user_name}'s AI Management Assistant for their company/employee/task dashboard.\n\n"
        f"Today: {today}\n"
        f"Current application week (Monday–Sunday): {week_start.isoformat()} to {week_end.isoformat()}\n\n"
        f"{owner_profile}\n\n"
        "LIVE APP DATABASE:\n"
        f"{app_knowledge}\n\n"
        f"Last company discussed: {last_co}; last employee: {last_emp}.\n\n"
        "MANAGE MODE:\n"
        "- Use tools only for clear management commands (create, add, list, update, delete).\n"
        "- To create a personal timetable/schedule, use generate_timetable (or the user can say "
        "'create my timetable' and you will generate it).\n"
        "- For personal chat or mentoring, reply in plain text WITHOUT tools.\n"
        "- Never create or change data unless the user clearly asked.\n\n"
    )

    return base + (
        "TOOL CALLING (required for actions):\n"
        "- Use the native tool/function calling API only.\n"
        "- Put the tool name in the function name field and arguments as a JSON object string.\n"
        "- Do NOT use XML formats like <function=...> and do NOT put JSON inside the tool name.\n"
        "- Only call tools when the user asks you to DO something (create, add, list, update, delete).\n"
        "- For greetings, mentoring, or personal conversation, reply in plain text WITHOUT calling any tools.\n\n"
        "RULES:\n"
        "- You MUST use the provided tools to read or change data. Never invent companies, employees, or tasks.\n"
        "- Never claim an action succeeded unless the tool returned success.\n"
        "- If a tool returns needs_confirmation, explain the impact and ask the user to confirm. "
        "Only call delete tools with confirmed=true after explicit user confirmation.\n"
        "- If company or employee is ambiguous or missing, ask one short clarification question.\n"
        "- For read-only questions (lists, counts, pending tasks), use list/get tools first.\n"
        "- Creating a company automatically creates its group chat — do not create duplicate groups.\n"
        "- Products, services, and earnings belong to a specific company — always set or infer the company.\n"
        "- Use create_product, create_service, and create_earning for catalog and earnings actions.\n"
        "- For the admin's personal timetable (My Timetable), use generate_timetable, list_timetable, "
        "create_timetable_item, update_timetable_item, delete_timetable_item, reset_timetable, "
        "planner_what_next, create_planner_goal, update_planner_notes, and get_planner_snapshot.\n"
        "- Timetable is personal CEO planning — not employee tasks. Prioritize using app snapshot data.\n"
        "- After completing actions, summarize clearly: what was created/updated/deleted, with names and roles.\n"
        "- Keep responses concise but complete. Use bullet lists for employees and tasks when helpful.\n"
        "- You only operate for the authenticated admin; all tools are already authorized.\n"
    )


def _assistant_message_dict(message):
    """Convert Groq assistant message to OpenAI-style dict for the next request."""
    tool_calls = []
    if message.tool_calls:
        for tc in message.tool_calls:
            name, args = _normalize_tool_call(tc.function.name, tc.function.arguments or "{}")
            tool_calls.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                }
            )

    out = {"role": "assistant", "content": message.content or ""}
    if tool_calls:
        out["tool_calls"] = tool_calls
    return out


def _recover_tool_calls_from_error(exc, context, messages):
    """Execute a mangled tool call only when the user explicitly asked for an action."""
    last_user = _last_user_message(messages)
    if not _user_wants_action(last_user):
        return False

    failed = _extract_failed_generation(exc)
    if not failed:
        return False
    name, args = _parse_failed_generation(failed)
    if not name:
        name, args = _normalize_tool_call(
            failed.replace("<function=", "").split(">")[0],
            "{}",
        )
        if "=" in name or "," in name:
            name, recovered = _split_mangled_tool_name(name)
            if recovered:
                args = recovered
    if not name or name not in _KNOWN_TOOL_NAMES:
        return False

    tool_id = f"call_recover_{uuid.uuid4().hex[:12]}"
    stub = _ToolCallStub(tool_id, name, args or "{}")
    tool_result = execute_tool_call(stub, context)
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args or "{}"},
                }
            ],
        }
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": tool_result,
        }
    )
    return True


def _chat_without_tools(client, model, messages, max_tokens=512):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def _run_mentor_chat(client, model, system, user_messages, max_tokens=1200):
    messages = [{"role": "system", "content": system}] + list(user_messages)
    text = _chat_without_tools(client, model, messages, max_tokens=max_tokens)
    return text or "I'm here to listen. What's on your mind?"


def _run_chat_only(client, model, system, user_text):
    return _run_mentor_chat(
        client,
        model,
        system,
        [{"role": "user", "content": user_text}],
        max_tokens=512,
    )


def _groq_create(client, **kwargs):
    return client.chat.completions.create(**kwargs)


def run_agent(user_messages, context, mode="chat", admin_id=None):
    """
    Run the agent loop. user_messages excludes system prompt.
    mode: 'chat' (mentor, no tools) or 'manage' (tools for explicit commands).
    admin_id: logged-in admin — used for owner profile in the system prompt.
    Returns assistant reply text.
    """
    config = get_active_groq_config()
    if not config:
        raise RuntimeError("No Groq API key configured. Add one in Admin → AI.")

    api_key = config["api_key"]
    model = config["model"]

    from groq import Groq

    client = Groq(api_key=api_key)
    week_start, week_end = get_week_bounds()
    mode = (mode or "chat").strip().lower()
    if mode not in ("chat", "manage"):
        mode = "chat"

    current_message = _last_user_message(user_messages)
    user_messages = _compress_messages_for_api(user_messages, mode)
    current_message = _last_user_message(user_messages)

    # Manage mode — timetable requests: generate directly (reliable; no tool-call parsing)
    if mode == "manage" and _is_timetable_request(current_message):
        try:
            reply = _run_timetable_generate_reply(current_message, admin_id)
            return reply
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise RuntimeError(_friendly_api_error(exc))
            raise RuntimeError(f"Could not generate timetable: {exc}") from exc

    # Chat mode: mentor conversation only — never use tools
    if mode == "chat":
        system = _build_system_prompt(context, week_start, week_end, mode="chat", admin_id=admin_id)
        try:
            reply = _run_mentor_chat(client, model, system, user_messages)
            mark_key_used(config.get("key_id"))
            return reply
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise RuntimeError(_friendly_api_error(exc))
            raise

    # Manage mode without explicit command: mentor-style reply, no tools
    if not _user_wants_management_action(current_message):
        system = _build_system_prompt(context, week_start, week_end, mode="chat", admin_id=admin_id)
        system += (
            "\nThe user is in Manage mode but did not give a clear create/list/update command. "
            "Respond helpfully without using tools. "
            "If they want app changes, ask them to state it clearly (e.g. 'Create company X').\n"
        )
        try:
            reply = _run_mentor_chat(client, model, system, user_messages)
            mark_key_used(config.get("key_id"))
            return reply
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise RuntimeError(_friendly_api_error(exc))
            raise

    # Manage mode with explicit command: tool loop
    if _is_small_talk(current_message):
        system = _build_system_prompt(context, week_start, week_end, mode="chat", admin_id=admin_id)
        try:
            reply = _run_chat_only(client, model, system, current_message)
            mark_key_used(config.get("key_id"))
            return reply
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise RuntimeError(_friendly_api_error(exc))
            raise

    system = _build_system_prompt(context, week_start, week_end, mode="manage", admin_id=admin_id)
    messages = [{"role": "system", "content": system}] + list(user_messages)
    tools = TOOL_DEFINITIONS
    max_iterations = 14

    for _ in range(max_iterations):
        try:
            response = _groq_create(
                client,
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise RuntimeError(_friendly_api_error(exc))
            if _is_tool_use_failed(exc):
                if _recover_tool_calls_from_error(exc, context, messages):
                    continue
                # Malformed tool output but user did not ask for an action — plain chat reply
                trimmed = [
                    messages[0],
                    {"role": "user", "content": current_message},
                ]
                text = _chat_without_tools(client, model, trimmed, max_tokens=512)
                mark_key_used(config.get("key_id"))
                return text or "How can I help you today?"
            raise

        message = response.choices[0].message

        if message.tool_calls:
            messages.append(_assistant_message_dict(message))
            for tc in message.tool_calls:
                name, args = _normalize_tool_call(tc.function.name, tc.function.arguments or "{}")
                tool_id = tc.id or f"call_{uuid.uuid4().hex[:12]}"

                if name in _WRITE_TOOL_NAMES and not _user_wants_management_action(current_message):
                    tool_result = json.dumps({
                        "success": False,
                        "error": "Skipped: user did not request a data change. Reply in plain text only.",
                    })
                else:
                    stub = _ToolCallStub(tool_id, name, args)
                    tool_result = execute_tool_call(stub, context)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": tool_result,
                    }
                )
            continue

        if message.content:
            mark_key_used(config.get("key_id"))
            return (message.content or "").strip()

        mark_key_used(config.get("key_id"))
        return "Done."

    mark_key_used(config.get("key_id"))
    return "I needed too many steps for that request. Please try breaking it into smaller parts."
