"""Full Mentor context snapshot from live app data."""

import json
from datetime import datetime, timedelta

from models import (
    MentorProblem,
    MentorSettings,
    OpportunityItem,
    OpportunityReport,
    OpportunityUserState,
    TimetableItem,
)
from services.app_knowledge import build_ai_app_knowledge_text
from services.app_time import app_now, app_today
from services.owner_profile_service import build_ai_owner_profile_text
from services.planner_snapshot import build_planner_snapshot, period_keys_for
from services.planner_service import list_timetable_for_date, timetable_progress


def _parse_hm(value):
    try:
        parts = (value or "00:00").split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def _minutes_between(start_hm, end_hm, now_hm):
    sh, sm = _parse_hm(start_hm)
    eh, em = _parse_hm(end_hm)
    nh, nm = _parse_hm(now_hm)
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    now_m = nh * 60 + nm
    if now_m < start_m:
        return None, end_m - start_m
    if now_m > end_m:
        return 0, 0
    return end_m - now_m, end_m - start_m


def _timetable_focus(items, now_hm):
    current = None
    next_item = None
    for item in sorted(items, key=lambda i: i.start_time):
        if item.completed:
            continue
        rem, total = _minutes_between(item.start_time, item.end_time, now_hm)
        if rem is not None and rem > 0 and _parse_hm(item.start_time) <= _parse_hm(now_hm):
            current = {
                "id": item.id,
                "title": item.title,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "minutes_remaining": rem,
                "duration_minutes": total,
            }
            break
        if _parse_hm(item.start_time) > _parse_hm(now_hm) and not next_item:
            next_item = {
                "id": item.id,
                "title": item.title,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
    return current, next_item


def _today_opportunities(limit=8):
    report = OpportunityReport.query.filter_by(
        report_date=app_today(), status="complete"
    ).first()
    if not report:
        return []
    items = (
        OpportunityItem.query.filter_by(report_id=report.id)
        .order_by(OpportunityItem.priority.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": o.id,
            "title": o.title,
            "venture_key": o.venture_key,
            "priority": o.priority,
            "deadline_date": o.deadline_date.isoformat() if o.deadline_date else None,
            "apply_url": o.apply_url or o.source_url,
            "company_id": o.company_id,
        }
        for o in items
    ]


def _saved_opportunities(admin_id, limit=5):
    rows = (
        OpportunityUserState.query.filter_by(admin_id=admin_id, status="saved")
        .order_by(OpportunityUserState.updated_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        if row.opportunity:
            o = row.opportunity
            result.append({
                "id": o.id,
                "title": o.title,
                "deadline_date": o.deadline_date.isoformat() if o.deadline_date else None,
            })
    return result


def build_mentor_snapshot(admin_id=None):
    now = app_now()
    today = now.date()
    now_hm = now.strftime("%H:%M")
    keys = period_keys_for(today)

    items = list_timetable_for_date(today)
    current, next_item = _timetable_focus(items, now_hm)
    prog = timetable_progress(items)

    problems = []
    if admin_id:
        problems = [
            p.to_dict()
            for p in MentorProblem.query.filter_by(admin_id=admin_id, status="open").all()
        ]

    settings_row = None
    if admin_id:
        settings_row = MentorSettings.query.filter_by(admin_id=admin_id).first()

    settings_dict = {
        "quiet_start": "22:00",
        "quiet_end": "07:00",
        "reminder_interval_minutes": 30,
        "max_reminders": 3,
        "voice_responses": True,
        "proactive_enabled": True,
        "context_notes": "",
    }
    if settings_row:
        settings_dict = settings_row.to_dict()

    planner = build_planner_snapshot(today)

    return {
        "now": {
            "datetime": now.isoformat(),
            "date": today.isoformat(),
            "time": now_hm,
            "weekday": now.strftime("%A"),
        },
        "owner_profile": build_ai_owner_profile_text(admin_id),
        "app_knowledge": build_ai_app_knowledge_text(),
        "mentor_context_notes": settings_dict.get("context_notes") or "",
        "period_keys": keys,
        "planner_snapshot": planner,
        "timetable": {
            "date": today.isoformat(),
            "progress": prog,
            "items": [
                {
                    "id": i.id,
                    "start_time": i.start_time,
                    "end_time": i.end_time,
                    "title": i.title,
                    "completed": i.completed,
                    "priority": i.priority,
                    "category": i.category,
                }
                for i in items
            ],
            "current_focus": current,
            "next_up": next_item,
        },
        "problems": problems,
        "opportunities_today": _today_opportunities(),
        "saved_opportunities": _saved_opportunities(admin_id) if admin_id else [],
        "settings": settings_dict,
    }


def snapshot_text_for_ai(snapshot, max_chars=12000):
    """Compact text block for Groq system prompt."""
    parts = [
        f"CURRENT DATE/TIME: {snapshot['now']['datetime']} ({snapshot['now']['weekday']})",
        snapshot.get("owner_profile", ""),
        f"MENTOR NOTES FROM USER: {snapshot.get('mentor_context_notes') or 'None'}",
        "LIVE APP DATA:",
        snapshot.get("app_knowledge", "")[:5000],
        "PLANNER SNAPSHOT:",
        json.dumps(snapshot.get("planner_snapshot", {}), ensure_ascii=False)[:4000],
        "TODAY TIMETABLE:",
        json.dumps(snapshot.get("timetable", {}), ensure_ascii=False),
        "ACTIVE PROBLEMS:",
        json.dumps(snapshot.get("problems", []), ensure_ascii=False),
        "TOP OPPORTUNITIES:",
        json.dumps(snapshot.get("opportunities_today", []), ensure_ascii=False),
    ]
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
