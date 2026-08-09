"""Groq-powered management agent with tool calling."""

import json
import re
import uuid
from datetime import date

from models import get_week_bounds
from services.ai_tools import TOOL_DEFINITIONS, execute_tool_call
from services.groq_key_service import get_active_groq_config, mark_key_used

_KNOWN_TOOL_NAMES = {t["function"]["name"] for t in TOOL_DEFINITIONS}

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
    "create", "add", "delete", "remove", "list", "show", "assign", "task",
    "company", "employee", "product", "service", "earning", "timetable", "planner",
)


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
    lower = t.lower()
    if len(t) < 48 and len(t.split()) <= 4:
        return not any(word in lower for word in _ACTION_WORDS)
    return False


def _build_system_prompt(context, week_start, week_end):
    last_co = context.get("last_company_name") or "none"
    last_emp = context.get("last_employee_name") or "none"
    today = date.today().isoformat()

    return (
        "You are the AI Management Assistant for an admin company/employee/task dashboard. "
        "You help the admin manage companies, employees, and weekly tasks using natural language.\n\n"
        f"Today: {today}\n"
        f"Current application week (Monday–Sunday): {week_start.isoformat()} to {week_end.isoformat()}\n"
        "When the user says 'this week', assign tasks for this week using create_tasks (week is automatic).\n\n"
        f"Conversation context — last company discussed: {last_co}; last employee: {last_emp}. "
        "Use these when the user says 'it', 'them', 'him', 'her', or 'that company' without repeating names.\n\n"
        "TOOL CALLING (required):\n"
        "- Use the native tool/function calling API only.\n"
        "- Put the tool name in the function name field and arguments as a JSON object string.\n"
        "- Do NOT use XML formats like <function=...> and do NOT put JSON inside the tool name.\n\n"
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
        "- For greetings or small talk, reply briefly without calling tools unless the user asks for action.\n"
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


def _chat_without_tools(client, model, messages):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


def run_agent(user_messages, context):
    """
    Run the agent loop. user_messages excludes system prompt.
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
    system = _build_system_prompt(context, week_start, week_end)

    messages = [{"role": "system", "content": system}] + list(user_messages)
    tools = TOOL_DEFINITIONS
    max_iterations = 14

    for _ in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as exc:
            if _is_tool_use_failed(exc):
                last_user = _last_user_message(messages)
                if _is_small_talk(last_user):
                    text = _chat_without_tools(client, model, messages)
                    mark_key_used(config.get("key_id"))
                    return text or "Hello! How can I help you manage your companies, employees, or tasks today?"
                if _recover_tool_calls_from_error(exc, context, messages):
                    continue
            raise

        message = response.choices[0].message

        if message.tool_calls:
            # Normalize before follow-up turns so Groq validates tool names correctly
            messages.append(_assistant_message_dict(message))
            for tc in message.tool_calls:
                name, args = _normalize_tool_call(tc.function.name, tc.function.arguments or "{}")
                tool_id = tc.id or f"call_{uuid.uuid4().hex[:12]}"
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
