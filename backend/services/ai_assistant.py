"""Groq-powered management agent with tool calling."""

from datetime import date

from flask import current_app

from models import get_week_bounds
from services.ai_tools import TOOL_DEFINITIONS, execute_tool_call


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
            tool_calls.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
            )

    out = {"role": "assistant", "content": message.content or ""}
    if tool_calls:
        out["tool_calls"] = tool_calls
    return out


def run_agent(user_messages, context):
    """
    Run the agent loop. user_messages excludes system prompt.
    Returns assistant reply text.
    """
    api_key = current_app.config.get("GROQ_API_KEY")
    model = current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    from groq import Groq

    client = Groq(api_key=api_key)
    week_start, week_end = get_week_bounds()
    system = _build_system_prompt(context, week_start, week_end)

    messages = [{"role": "system", "content": system}] + list(user_messages)
    tools = TOOL_DEFINITIONS
    max_iterations = 14

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=2048,
        )

        message = response.choices[0].message
        messages.append(_assistant_message_dict(message))

        if not message.tool_calls:
            return (message.content or "").strip()

        for tool_call in message.tool_calls:
            tool_result = execute_tool_call(tool_call, context)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

    return "I needed too many steps for that request. Please try breaking it into smaller parts."
