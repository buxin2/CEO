"""Mentor AI chat, advice, and tool actions."""

import json
import re
from datetime import datetime, timedelta

from services.groq_key_service import get_active_groq_config, is_groq_configured, mark_key_used
from services.mentor_snapshot import build_mentor_snapshot, snapshot_text_for_ai
from services.mentor_service import (
    add_message,
    create_checkin,
    create_problem,
    get_mentor_settings,
    list_messages,
    update_problem,
    update_mentor_settings,
)
from services.owner_profile_service import build_name_address_rules, resolve_owner_display_name
from services.app_time import app_now


def build_mentor_system(admin_id=None):
    name = resolve_owner_display_name(admin_id)
    return (
        f"You are {name}'s personal Mentor — advisor, accountability partner, and strategic guide.\n"
        + build_name_address_rules(admin_id)
        + "\n"
        "You know their companies, timetable, earnings, tasks, opportunities, and problems.\n"
        "Be supportive, honest, direct, and practical. Never insulting or manipulative.\n"
        "Give ONE clear priority at a time — do not overwhelm with long lists.\n"
        "Use LIVE DATA below. Never invent companies, earnings, or deadlines.\n"
        "When the user completes something, acknowledge and give the next step.\n"
        "You can use tools to create problems, schedule reminders, update timetable, and generate schedules.\n"
        "For destructive actions, ask confirmation first.\n"
    )

MENTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "schedule_reminder",
            "description": "Schedule a Mentor check-in/reminder at a specific time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "scheduled_at": {"type": "string", "description": "ISO datetime local intent"},
                    "title": {"type": "string"},
                },
                "required": ["message", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_problem",
            "description": "Record an active business problem to track.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "company_id": {"type": "integer"},
                    "priority": {"type": "string"},
                    "next_action": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_problem",
            "description": "Mark a mentor problem as resolved.",
            "parameters": {
                "type": "object",
                "properties": {"problem_id": {"type": "integer"}},
                "required": ["problem_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_timetable_item",
            "description": "Mark a timetable item as completed.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_timetable_item",
            "description": "Add an item to the personal timetable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_timetable",
            "description": "AI-generate full day timetable for a date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_date": {"type": "string"},
                    "replace_existing": {"type": "boolean"},
                    "instructions": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_context_note",
            "description": "Remember something the user said for future advice (append to mentor notes).",
            "parameters": {
                "type": "object",
                "properties": {"note": {"type": "string"}},
                "required": ["note"],
            },
        },
    },
]


def _parse_json(content):
    text = (content or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return json.loads(text)


def _execute_mentor_tool(name, args, admin_id):
    from models import TimetableItem
    from services.planner_service import create_timetable_item
    from services.planner_ai import generate_timetable_with_ai
    from services.app_time import app_today, parse_date_iso

    if name == "schedule_reminder":
        when = args.get("scheduled_at")
        try:
            scheduled = datetime.fromisoformat(when.replace("Z", ""))
        except ValueError:
            scheduled = app_now() + timedelta(hours=1)
        row = create_checkin(
            admin_id,
            args.get("message") or "Reminder",
            scheduled,
            title=(args.get("title") or "")[:500],
        )
        return {"success": True, "check_in_id": row.id, "scheduled_at": scheduled.isoformat()}

    if name == "create_problem":
        p = create_problem(admin_id, args)
        return {"success": True, "problem": p.to_dict()}

    if name == "resolve_problem":
        pid = int(args.get("problem_id"))
        p = update_problem(pid, admin_id, {"status": "resolved"})
        return {"success": True, "problem": p.to_dict()}

    if name == "complete_timetable_item":
        item = TimetableItem.query.get(int(args["item_id"]))
        if not item:
            return {"error": "Timetable item not found."}
        item.completed = True
        from models import db

        db.session.commit()
        return {"success": True, "title": item.title}

    if name == "create_timetable_item":
        plan_date = parse_date_iso(args.get("plan_date")) or app_today()
        item = create_timetable_item(plan_date, args)
        return {"success": True, "item": item.to_dict()}

    if name == "generate_timetable":
        plan_date = parse_date_iso(args.get("plan_date")) or app_today()
        result = generate_timetable_with_ai(
            plan_date,
            replace_existing=bool(args.get("replace_existing")),
            extra_instructions=args.get("instructions") or "",
        )
        return {"success": True, "summary": result}

    if name == "save_context_note":
        s = get_mentor_settings(admin_id)
        note = (args.get("note") or "").strip()
        if note:
            existing = (s.context_notes or "").strip()
            s.context_notes = (existing + "\n" + note).strip()[:5000]
            from models import db

            db.session.commit()
        return {"success": True}

    return {"error": f"Unknown tool: {name}"}


def _chat_messages_for_api(admin_id, user_message, history_limit=12):
    prior = list_messages(admin_id, limit=history_limit)
    messages = []
    for m in prior:
        if m.role == "user":
            messages.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            messages.append({"role": "assistant", "content": m.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def mentor_chat(admin_id, message):
    if not is_groq_configured():
        return "Add a Groq API key in Admin → AI Assistant to use Mentor."

    config = get_active_groq_config()
    snapshot = build_mentor_snapshot(admin_id)
    context = snapshot_text_for_ai(snapshot)

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    system = build_mentor_system(admin_id) + "\n\n" + context
    messages = [{"role": "system", "content": system}] + _chat_messages_for_api(admin_id, message)

    for _ in range(6):
        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            tools=MENTOR_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=1200,
        )
        mark_key_used(config.get("key_id"))
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _execute_mentor_tool(tc.function.name, args, admin_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
            continue

        reply = (msg.content or "").strip()
        add_message(admin_id, "user", message)
        add_message(admin_id, "assistant", reply)
        return reply

    return "I need a moment — please try again."


def mentor_what_now(admin_id):
    if not is_groq_configured():
        return {"error": "Groq API not configured."}

    config = get_active_groq_config()
    snapshot = build_mentor_snapshot(admin_id)
    context = snapshot_text_for_ai(snapshot)

    prompt = (
        f"Based on CURRENT DATE/TIME and all data, answer: What should {resolve_owner_display_name(admin_id)} do RIGHT NOW?\n"
        "Return JSON only:\n"
        '{"title":"...","why":"...","start_time":"HH:MM optional","end_time":"HH:MM optional",'
        '"duration_minutes":45,"action_label":"Start","timetable_item_id":null or int}'
    )

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": build_mentor_system(admin_id) + "\n" + context},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=800,
    )
    mark_key_used(config.get("key_id"))
    raw = response.choices[0].message.content or "{}"
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        data = {"title": raw, "why": "", "action_label": "Start"}
    return data


def mentor_advice(admin_id):
    if not is_groq_configured():
        return "Configure Groq API for Mentor advice."

    config = get_active_groq_config()
    snapshot = build_mentor_snapshot(admin_id)
    context = snapshot_text_for_ai(snapshot)

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": build_mentor_system(admin_id) + "\n" + context},
            {
                "role": "user",
                "content": "Give one short paragraph of Mentor advice for right now. Be specific.",
            },
        ],
        temperature=0.45,
        max_tokens=400,
    )
    mark_key_used(config.get("key_id"))
    return (response.choices[0].message.content or "").strip()


def mentor_daily_review(admin_id, kind="evening"):
    if not is_groq_configured():
        return "Configure Groq API."

    config = get_active_groq_config()
    snapshot = build_mentor_snapshot(admin_id)
    context = snapshot_text_for_ai(snapshot)
    label = "morning briefing" if kind == "morning" else "end-of-day review"

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": build_mentor_system(admin_id) + "\n" + context},
            {
                "role": "user",
                "content": f"Provide a {label}: progress, what went well, needs attention, top 3 priorities. Concise.",
            },
        ],
        temperature=0.4,
        max_tokens=900,
    )
    mark_key_used(config.get("key_id"))
    text = (response.choices[0].message.content or "").strip()
    add_message(admin_id, "assistant", text, {"kind": kind})
    return text


def parse_reminder_from_message(message):
    """Simple 'remind me in 2 hours' parser."""
    m = re.search(r"remind(?: me)?(?: in| at)?\s+(\d+)\s*(minute|hour|hr|min)s?", message, re.I)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(minutes=n) if unit.startswith("min") else timedelta(hours=n)
        return app_now() + delta
    return None
