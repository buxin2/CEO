"""AI-powered timetable generation using Groq."""

import json
from datetime import date, datetime

from flask import current_app

from models import get_week_bounds
from services.planner_snapshot import build_planner_snapshot, period_keys_for
from services.planner_service import (
    create_timetable_item,
    reset_timetable_for_date,
    resolve_company_id,
    get_planner_settings,
    list_timetable_for_date,
)


def _parse_plan_json(content):
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def generate_timetable_with_ai(plan_date, replace_existing=False, extra_instructions=""):
    from services.groq_key_service import get_active_groq_config, mark_key_used

    config = get_active_groq_config()
    if not config:
        raise RuntimeError("No Groq API key configured. Add one in Admin → AI.")

    api_key = config["api_key"]
    model = config["model"]

    from groq import Groq

    snapshot = build_planner_snapshot(plan_date)
    settings = get_planner_settings()
    existing = list_timetable_for_date(plan_date)
    keys = period_keys_for(plan_date)

    prompt = (
        "You are a personal executive assistant creating a realistic full-day timetable for an admin/CEO. "
        "Use the application snapshot to prioritize what matters NOW — low earnings, pending tasks, "
        "unfinished work, company priorities. Do NOT copy employee tasks verbatim; reason about priorities.\n\n"
        f"Plan date: {plan_date.isoformat()}\n"
        f"Period keys: {json.dumps(keys)}\n"
        f"Personal notes from admin: {settings.personal_notes or 'None'}\n"
        f"Extra instructions: {extra_instructions or 'None'}\n"
        f"Application snapshot: {json.dumps(snapshot)}\n"
    )
    if existing:
        prompt += f"Existing items on this date ({len(existing)}): use replace mode — create a fresh schedule.\n"

    prompt += (
        "\nReturn ONLY valid JSON with this structure:\n"
        '{"today_focus": ["string"], "items": ['
        '{"start_time":"07:00","end_time":"08:00","title":"...","description":"why and what to do",'
        '"priority":"high|medium|low","category":"work|meal|break|exercise|personal|planning|development|business|sleep|communication|meeting|learning|travel",'
        '"link_type":"none|company|company_group|company_tasks|company_earnings|dashboard|ai_assistant",'
        '"link_company_name":"optional company name if link_type needs company","link_label":"button label"}]}\n'
        "Create a realistic day from roughly 6 AM to 10 PM with meals, breaks, and sleep. "
        "Include 10-18 items. Link to real companies from the snapshot when relevant."
    )

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You output only valid JSON for timetable planning."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = _parse_plan_json(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI returned invalid JSON: {exc}") from exc

    if replace_existing:
        reset_timetable_for_date(plan_date)

    created = []
    for entry in data.get("items") or []:
        link_type = (entry.get("link_type") or "none").lower()
        link_company_id = None
        if link_type not in ("none", "dashboard", "ai_assistant"):
            link_company_id = resolve_company_id(entry.get("link_company_name"))
            if not link_company_id and snapshot.get("companies"):
                link_company_id = snapshot["companies"][0]["id"]

        item = create_timetable_item(
            plan_date,
            {
                "start_time": entry.get("start_time"),
                "end_time": entry.get("end_time"),
                "title": entry.get("title"),
                "description": entry.get("description"),
                "priority": entry.get("priority"),
                "category": entry.get("category"),
                "link_type": link_type,
                "link_company_id": link_company_id,
                "link_label": entry.get("link_label"),
            },
        )
        created.append(item)

    mark_key_used(config.get("key_id"))

    return {
        "today_focus": data.get("today_focus") or [],
        "items_created": len(created),
        "plan_date": plan_date.isoformat(),
    }


def suggest_next_activity(plan_date=None, current_time=None):
    """Suggest what to do now based on timetable and time."""
    from services.groq_key_service import get_active_groq_config, mark_key_used

    config = get_active_groq_config()
    if not config:
        raise RuntimeError("No Groq API key configured. Add one in Admin → AI.")

    from groq import Groq

    api_key = config["api_key"]
    model = config["model"]

    plan_date = plan_date or date.today()
    if current_time is None:
        current_time = datetime.now().strftime("%H:%M")

    snapshot = build_planner_snapshot(plan_date)
    items = list_timetable_for_date(plan_date)
    items_data = [i.to_dict(include_link=True) for i in items]

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You advise an admin CEO on what to focus on next. Be concise and actionable.",
            },
            {
                "role": "user",
                "content": (
                    f"Current time: {current_time} on {plan_date.isoformat()}\n"
                    f"Timetable: {json.dumps(items_data)}\n"
                    f"App snapshot: {json.dumps(snapshot)}\n"
                    "What should I do now or next? Reference timetable item ids if suggesting completion."
                ),
            },
        ],
        temperature=0.3,
        max_tokens=800,
    )

    mark_key_used(config.get("key_id"))
    return (response.choices[0].message.content or "").strip()
