"""Planner CRUD and link helpers."""

import re
from datetime import date, datetime

from sqlalchemy import func

from models import db, Company, PlannerGoal, TimetableItem, PlannerSettings, get_week_bounds
from services.planner_snapshot import period_keys_for
from utils import frontend_url, group_link_for_token, create_group_for_company


TIME_RE = re.compile(r"^\d{2}:\d{2}$")
VALID_PRIORITIES = ("high", "medium", "low")
VALID_LINK_TYPES = (
    "none",
    "company",
    "company_group",
    "company_tasks",
    "company_earnings",
    "dashboard",
    "ai_assistant",
)
VALID_CATEGORIES = (
    "work",
    "business",
    "development",
    "meeting",
    "meal",
    "break",
    "exercise",
    "personal",
    "planning",
    "learning",
    "sleep",
    "travel",
    "communication",
)


def get_planner_settings():
    settings = PlannerSettings.query.first()
    if not settings:
        settings = PlannerSettings(personal_notes="")
        db.session.add(settings)
        db.session.commit()
    return settings


def normalize_time(value, default="09:00"):
    val = (value or default).strip()
    if TIME_RE.match(val):
        return val
    return default


def build_item_link_url(item):
    lt = item.link_type or "none"
    if lt == "company" and item.link_company_id:
        return frontend_url(f"company.html?id={item.link_company_id}")
    if lt == "company_group" and item.link_company_id:
        company = Company.query.get(item.link_company_id)
        if company:
            group = company.group or create_group_for_company(company)
            if not company.group:
                db.session.add(group)
                db.session.commit()
            return frontend_url(
                f"group.html?token={group.group_token}&company_id={company.id}"
            )
    if lt == "company_tasks" and item.link_company_id:
        return frontend_url(f"company.html?id={item.link_company_id}")
    if lt == "company_earnings" and item.link_company_id:
        return frontend_url(f"company.html?id={item.link_company_id}")
    if lt == "dashboard":
        return frontend_url("dashboard.html")
    if lt == "ai_assistant":
        return frontend_url("ai-assistant.html")
    return ""


def serialize_item(item):
    return item.to_dict(include_link=True)


def list_goals(scope, period_key):
    return (
        PlannerGoal.query.filter_by(scope=scope, period_key=period_key)
        .order_by(PlannerGoal.position.asc(), PlannerGoal.id.asc())
        .all()
    )


def create_goal(scope, period_key, title):
    title = (title or "").strip()
    if not title:
        raise ValueError("Goal title is required.")
    max_pos = db.session.query(func.max(PlannerGoal.position)).filter_by(
        scope=scope, period_key=period_key
    ).scalar() or 0
    goal = PlannerGoal(
        scope=scope,
        period_key=period_key,
        title=title,
        position=max_pos + 1,
    )
    db.session.add(goal)
    db.session.commit()
    return goal


def update_goal(goal_id, **fields):
    goal = PlannerGoal.query.get(goal_id)
    if not goal:
        raise ValueError("Goal not found.")
    if fields.get("title") is not None:
        t = fields["title"].strip()
        if not t:
            raise ValueError("Goal title cannot be empty.")
        goal.title = t
    if fields.get("completed") is not None:
        goal.completed = bool(fields["completed"])
    db.session.commit()
    return goal


def delete_goal(goal_id):
    goal = PlannerGoal.query.get(goal_id)
    if not goal:
        raise ValueError("Goal not found.")
    db.session.delete(goal)
    db.session.commit()


def list_timetable_for_date(plan_date):
    items = (
        TimetableItem.query.filter_by(plan_date=plan_date)
        .order_by(TimetableItem.start_time.asc(), TimetableItem.position.asc())
        .all()
    )
    return items


def list_timetable_range(start_date, end_date):
    items = (
        TimetableItem.query.filter(
            TimetableItem.plan_date >= start_date,
            TimetableItem.plan_date <= end_date,
        )
        .order_by(TimetableItem.plan_date.asc(), TimetableItem.start_time.asc())
        .all()
    )
    return items


def timetable_progress(items):
    total = len(items)
    done = len([i for i in items if i.completed])
    pct = round((done / total) * 100) if total else 0
    return {"total": total, "completed": done, "pending": total - done, "completion_pct": pct}


def create_timetable_item(plan_date, data):
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required.")

    priority = (data.get("priority") or "medium").lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    category = (data.get("category") or "work").lower()
    if category not in VALID_CATEGORIES:
        category = "work"

    link_type = (data.get("link_type") or "none").lower()
    if link_type not in VALID_LINK_TYPES:
        link_type = "none"

    link_company_id = data.get("link_company_id")
    if link_company_id:
        link_company_id = int(link_company_id)
        if not Company.query.get(link_company_id):
            raise ValueError("Linked company not found.")

    max_pos = db.session.query(func.max(TimetableItem.position)).filter_by(
        plan_date=plan_date
    ).scalar() or 0

    item = TimetableItem(
        plan_date=plan_date,
        start_time=normalize_time(data.get("start_time"), "09:00"),
        end_time=normalize_time(data.get("end_time"), "10:00"),
        title=title,
        description=(data.get("description") or "").strip(),
        priority=priority,
        category=category,
        link_type=link_type,
        link_company_id=link_company_id if link_type != "none" else None,
        link_label=(data.get("link_label") or "").strip(),
        position=max_pos + 1,
    )
    db.session.add(item)
    db.session.commit()
    return item


def update_timetable_item(item_id, data):
    item = TimetableItem.query.get(item_id)
    if not item:
        raise ValueError("Timetable item not found.")

    if data.get("title") is not None:
        t = data["title"].strip()
        if not t:
            raise ValueError("Title cannot be empty.")
        item.title = t
    if data.get("description") is not None:
        item.description = data["description"].strip()
    if data.get("start_time") is not None:
        item.start_time = normalize_time(data["start_time"], item.start_time)
    if data.get("end_time") is not None:
        item.end_time = normalize_time(data["end_time"], item.end_time)
    if data.get("priority") is not None:
        p = data["priority"].lower()
        if p in VALID_PRIORITIES:
            item.priority = p
    if data.get("category") is not None:
        c = data["category"].lower()
        if c in VALID_CATEGORIES:
            item.category = c
    if data.get("link_type") is not None:
        lt = data["link_type"].lower()
        if lt in VALID_LINK_TYPES:
            item.link_type = lt
    if data.get("link_company_id") is not None:
        cid = data["link_company_id"]
        if cid:
            cid = int(cid)
            if not Company.query.get(cid):
                raise ValueError("Linked company not found.")
            item.link_company_id = cid
        else:
            item.link_company_id = None
    if data.get("link_label") is not None:
        item.link_label = data["link_label"].strip()
    if data.get("completed") is not None:
        item.completed = bool(data["completed"])
    if data.get("plan_date") is not None:
        item.plan_date = datetime.strptime(data["plan_date"], "%Y-%m-%d").date()

    db.session.commit()
    return item


def delete_timetable_item(item_id):
    item = TimetableItem.query.get(item_id)
    if not item:
        raise ValueError("Timetable item not found.")
    db.session.delete(item)
    db.session.commit()


def reset_timetable_for_date(plan_date):
    TimetableItem.query.filter_by(plan_date=plan_date).delete()
    db.session.commit()


def resolve_company_id(name_or_id):
    if name_or_id is None:
        return None
    if isinstance(name_or_id, int) or str(name_or_id).isdigit():
        c = Company.query.get(int(name_or_id))
        return c.id if c else None
    name = str(name_or_id).strip()
    exact = Company.query.filter(Company.name.ilike(name)).first()
    if exact:
        return exact.id
    partial = Company.query.filter(Company.name.ilike(f"%{name}%")).all()
    if len(partial) == 1:
        return partial[0].id
    return None


def daily_summary(plan_date):
    items = list_timetable_for_date(plan_date)
    prog = timetable_progress(items)
    completed = [i.title for i in items if i.completed]
    not_completed = [i.title for i in items if not i.completed]
    return {
        "date": plan_date.isoformat(),
        "progress": prog,
        "completed_titles": completed,
        "not_completed_titles": not_completed,
    }
