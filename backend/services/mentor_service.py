"""Mentor CRUD, check-ins, and dashboard helpers."""

from datetime import datetime, timedelta

from models import db, Admin, MentorCheckIn, MentorMessage, MentorProblem, MentorSettings, TimetableItem
from services.app_time import app_now, app_today, parse_date_iso
from services.owner_profile_service import resolve_owner_display_name


def get_mentor_settings(admin_id):
    if not admin_id:
        admin = Admin.query.order_by(Admin.id.asc()).first()
        admin_id = admin.id if admin else None
    if not admin_id:
        return MentorSettings(
            quiet_start="22:00",
            quiet_end="07:00",
            reminder_interval_minutes=30,
            max_reminders=3,
            voice_responses=True,
            proactive_enabled=True,
        )
    row = MentorSettings.query.filter_by(admin_id=admin_id).first()
    if not row:
        row = MentorSettings(admin_id=admin_id)
        db.session.add(row)
        db.session.commit()
    return row


def update_mentor_settings(admin_id, data):
    s = get_mentor_settings(admin_id)
    if data.get("quiet_start"):
        s.quiet_start = data["quiet_start"][:5]
    if data.get("quiet_end"):
        s.quiet_end = data["quiet_end"][:5]
    if data.get("reminder_interval_minutes") is not None:
        s.reminder_interval_minutes = max(5, min(120, int(data["reminder_interval_minutes"])))
    if data.get("max_reminders") is not None:
        s.max_reminders = max(1, min(10, int(data["max_reminders"])))
    if data.get("voice_responses") is not None:
        s.voice_responses = bool(data["voice_responses"])
    if data.get("proactive_enabled") is not None:
        s.proactive_enabled = bool(data["proactive_enabled"])
    if data.get("context_notes") is not None:
        s.context_notes = (data["context_notes"] or "").strip()
    db.session.commit()
    return s


def list_problems(admin_id, status=None):
    q = MentorProblem.query.filter_by(admin_id=admin_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(MentorProblem.priority.asc(), MentorProblem.id.desc()).all()


def create_problem(admin_id, data):
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Problem title is required.")
    p = MentorProblem(
        admin_id=admin_id,
        company_id=data.get("company_id"),
        title=title[:500],
        description=(data.get("description") or "").strip(),
        status="open",
        priority=(data.get("priority") or "medium").lower(),
        next_action=(data.get("next_action") or "").strip(),
    )
    if data.get("follow_up_at"):
        try:
            p.follow_up_at = datetime.fromisoformat(data["follow_up_at"].replace("Z", ""))
        except ValueError:
            pass
    db.session.add(p)
    db.session.commit()
    return p


def update_problem(problem_id, admin_id, data):
    p = MentorProblem.query.filter_by(id=problem_id, admin_id=admin_id).first()
    if not p:
        raise ValueError("Problem not found.")
    if data.get("title"):
        p.title = data["title"].strip()[:500]
    if data.get("description") is not None:
        p.description = data["description"].strip()
    if data.get("status"):
        st = data["status"].lower()
        if st in ("open", "pending", "resolved"):
            p.status = st
            if st == "resolved":
                p.resolved_at = datetime.utcnow()
    if data.get("priority"):
        p.priority = data["priority"].lower()
    if data.get("next_action") is not None:
        p.next_action = data["next_action"].strip()
    if data.get("follow_up_at") is not None:
        if data["follow_up_at"]:
            p.follow_up_at = datetime.fromisoformat(data["follow_up_at"].replace("Z", ""))
        else:
            p.follow_up_at = None
    db.session.commit()
    return p


def add_message(admin_id, role, content, meta=None):
    import json

    msg = MentorMessage(
        admin_id=admin_id,
        role=role,
        content=content.strip(),
        meta_json=json.dumps(meta or {}),
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def list_messages(admin_id, limit=40):
    rows = (
        MentorMessage.query.filter_by(admin_id=admin_id)
        .order_by(MentorMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def list_pending_checkins(admin_id):
    now = datetime.utcnow()
    rows = (
        MentorCheckIn.query.filter_by(admin_id=admin_id)
        .filter(MentorCheckIn.status.in_(("pending", "sent")))
        .filter(MentorCheckIn.scheduled_at <= now + timedelta(hours=1))
        .order_by(MentorCheckIn.scheduled_at.asc())
        .limit(20)
        .all()
    )
    return rows


def create_checkin(admin_id, message, scheduled_at, kind="scheduled", title="", **kwargs):
    row = MentorCheckIn(
        admin_id=admin_id,
        kind=kind,
        title=(title or "")[:500],
        message=message.strip(),
        scheduled_at=scheduled_at,
        status="pending",
        timetable_item_id=kwargs.get("timetable_item_id"),
        problem_id=kwargs.get("problem_id"),
    )
    db.session.add(row)
    db.session.commit()
    return row


def respond_checkin(checkin_id, admin_id, response_type, response_text=""):
    row = MentorCheckIn.query.filter_by(id=checkin_id, admin_id=admin_id).first()
    if not row:
        raise ValueError("Check-in not found.")
    row.status = "responded"
    row.response_type = (response_type or "").strip()[:40]
    row.response = (response_text or "").strip()
    if row.timetable_item_id and response_type in ("completed", "yes", "done"):
        item = TimetableItem.query.get(row.timetable_item_id)
        if item:
            item.completed = True
    db.session.commit()
    return row


def _in_quiet_hours(settings, now_local):
    """Check if now is within quiet hours (local app time)."""
    start = settings.quiet_start or "22:00"
    end = settings.quiet_end or "07:00"
    t = now_local.strftime("%H:%M")
    if start < end:
        return start <= t < end
    return t >= start or t < end


def process_due_checkins():
    """Activate pending check-ins and send reminder escalations."""
    from models import Admin

    now_utc = datetime.utcnow()
    admins = Admin.query.all()
    for admin in admins:
        settings = get_mentor_settings(admin.id)
        if not settings.proactive_enabled:
            continue
        now_local = app_now()
        if _in_quiet_hours(settings, now_local):
            continue

        due = MentorCheckIn.query.filter_by(admin_id=admin.id, status="pending").filter(
            MentorCheckIn.scheduled_at <= now_utc
        ).all()
        for row in due:
            row.status = "sent"
            add_message(
                admin.id,
                "proactive",
                row.message,
                {"check_in_id": row.id, "kind": row.kind},
            )

        stuck = MentorCheckIn.query.filter_by(admin_id=admin.id, status="sent").all()
        interval = settings.reminder_interval_minutes or 30
        max_rem = settings.max_reminders or 3
        for row in stuck:
            if row.reminder_count >= max_rem:
                row.status = "cancelled"
                continue
            age = (now_utc - row.scheduled_at).total_seconds() / 60
            needed = interval * (row.reminder_count + 1)
            if age >= needed:
                row.reminder_count += 1
                reminder = (
                    "Just checking in — I still need your update on this. "
                    f"({row.title or 'task'})"
                )
                add_message(
                    admin.id,
                    "proactive",
                    reminder,
                    {"check_in_id": row.id, "kind": "reminder"},
                )
    db.session.commit()


def schedule_hourly_timetable_checkins(admin_id):
    """Create check-in at start of each upcoming timetable block (today)."""
    settings = get_mentor_settings(admin_id)
    if not settings.proactive_enabled:
        return
    now = app_now()
    if _in_quiet_hours(settings, now):
        return

    today = now.date()
    now_hm = now.strftime("%H:%M")
    from services.planner_service import list_timetable_for_date

    items = list_timetable_for_date(today)
    for item in items:
        if item.completed or item.start_time <= now_hm:
            continue
        exists = MentorCheckIn.query.filter_by(
            admin_id=admin_id,
            timetable_item_id=item.id,
            kind="hourly",
        ).filter(MentorCheckIn.status != "cancelled").first()
        if exists:
            continue
        sh, sm = map(int, item.start_time.split(":"))
        scheduled = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        if scheduled < now:
            continue
        msg = (
            f"You planned **{item.title}** from {item.start_time} to {item.end_time}. "
            "Have you started?"
        )
        create_checkin(
            admin_id,
            msg,
            scheduled,
            kind="hourly",
            title=item.title,
            timetable_item_id=item.id,
        )


def build_dashboard(admin_id):
    from services.mentor_snapshot import build_mentor_snapshot

    snapshot = build_mentor_snapshot(admin_id)
    settings = get_mentor_settings(admin_id)
    problems = list_problems(admin_id, status="open")
    pending_checkins = [c.to_dict() for c in list_pending_checkins(admin_id)]
    messages = [m.to_dict() for m in list_messages(admin_id, limit=30)]

    tt = snapshot.get("timetable", {})
    planner = snapshot.get("planner_snapshot", {})

    return {
        "now": snapshot["now"],
        "display_name": resolve_owner_display_name(admin_id),
        "settings": settings.to_dict(),
        "right_now": tt.get("current_focus"),
        "next_up": tt.get("next_up"),
        "timetable_progress": tt.get("progress"),
        "timetable_items": tt.get("items", []),
        "problems": [p.to_dict() for p in problems],
        "opportunities": snapshot.get("opportunities_today", []),
        "saved_opportunities": snapshot.get("saved_opportunities", []),
        "goals": planner.get("goals", {}),
        "companies_summary": planner.get("companies", []),
        "totals": planner.get("totals", {}),
        "pending_checkins": pending_checkins,
        "messages": messages,
    }
