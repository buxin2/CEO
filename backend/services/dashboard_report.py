"""CEO dashboard: Excel work given, completed, leftover, and day reports."""

import logging
from datetime import date

from models import Company, Employee, Earning, WorkList, WorkListRow, db
from services.worklist_service import _as_date
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _is_done(row):
    return str(getattr(row, "status", "") or "").strip().lower() in ("done", "completed", "complete")


def _day_key(value):
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else ""


def _row_brief(row, employee, company):
    return {
        "id": row.id,
        "row_number": row.row_number,
        "title": row.title(),
        "status": "done" if _is_done(row) else (row.status or "pending"),
        "notes": (row.notes or "").strip(),
        "assigned_date": _day_key(row.assigned_date) or None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "employee_id": employee.id,
        "employee_name": employee.name,
        "company_id": company.id,
        "company_name": company.name,
    }


def _empty_report(day, error=None):
    return {
        "date": day.isoformat(),
        "error": error,
        "summary": {
            "excel_people": 0,
            "excel_lists": 0,
            "working_today": 0,
            "finished_today": 0,
            "on_track": 0,
            "lacking": 0,
            "all_given": 0,
            "all_done": 0,
            "all_open": 0,
            "today_given": 0,
            "today_done": 0,
            "today_open": 0,
            "leftover": 0,
            "earnings_total": 0,
            "earnings_count": 0,
        },
        "on_track": [],
        "lacking": [],
        "finished_today": [],
        "people": [],
        "companies": [],
        "completed_work": [],
        "open_work": [],
        "completed_any": [],
    }


def dashboard_work_report(day=None, include_details=True):
    day = day or date.today()
    day_iso = day.isoformat()
    try:
        lists = WorkList.query.order_by(WorkList.id.asc()).all()
        if not lists:
            raw = db.session.execute(text("SELECT COUNT(*) FROM work_lists")).scalar()
            if raw:
                lists = WorkList.query.all()
    except Exception as exc:
        logger.exception("Excel dashboard query failed")
        return _empty_report(day, error=str(exc))

    people = []
    company_stats = {}
    employees_by_id = {e.id: e for e in Employee.query.all()}
    companies_by_id = {c.id: c for c in Company.query.all()}

    for company in Company.query.order_by(Company.name.asc()).all():
        company_stats[company.id] = {
            "id": company.id,
            "name": company.name,
            "employee_count": company.employees.count(),
            "excel_people": 0,
            "excel_lists": 0,
            "all_given": 0,
            "all_done": 0,
            "today_given": 0,
            "today_done": 0,
            "leftover": 0,
            "on_track": 0,
            "lacking": 0,
        }

    lists_by_employee = {}
    for work in lists:
        lists_by_employee.setdefault(work.employee_id, []).append(work)

    for employee_id, emp_lists in lists_by_employee.items():
        employee = employees_by_id.get(employee_id)
        if not employee:
            continue
        company = companies_by_id.get(employee.company_id) or emp_lists[0].company
        if not company:
            continue
        ids = [w.id for w in emp_lists]
        assigned = (
            WorkListRow.query.filter(WorkListRow.work_list_id.in_(ids))
            .filter(WorkListRow.assigned_date.isnot(None))
            .all()
        )
        today_rows = [r for r in assigned if _day_key(r.assigned_date) == day_iso]
        leftover_rows = [
            r for r in assigned
            if _day_key(r.assigned_date) and _day_key(r.assigned_date) < day_iso and not _is_done(r)
        ]
        today_done_rows = [r for r in today_rows if _is_done(r)]
        today_open_rows = [r for r in today_rows if not _is_done(r)]
        done_this_day = [
            r for r in assigned
            if _is_done(r) and (
                (_as_date(r.completed_at) == day) if r.completed_at else _day_key(r.assigned_date) == day_iso
            )
        ]
        all_done_rows = [r for r in assigned if _is_done(r)]
        all_open_rows = [r for r in assigned if not _is_done(r)]
        today_given = len(today_rows)
        today_done = len(today_done_rows)
        leftover = len(leftover_rows)
        finished_today = today_given > 0 and today_done == today_given
        lacking = leftover > 0 or (today_given > 0 and today_done < today_given)
        person = {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "company_id": company.id,
            "company_name": company.name,
            "has_excel": True,
            "all_given": len(assigned),
            "all_done": len(all_done_rows),
            "all_open": len(all_open_rows),
            "today_given": today_given,
            "today_done": today_done,
            "today_open": len(today_open_rows),
            "leftover": leftover,
            "finished_today": finished_today,
            "on_track": (not lacking),
            "lacking": lacking,
        }
        if include_details:
            person["completed"] = [_row_brief(r, employee, company) for r in done_this_day]
            person["open"] = [_row_brief(r, employee, company) for r in today_open_rows]
            person["leftover_items"] = [_row_brief(r, employee, company) for r in leftover_rows]
            person["completed_any"] = [_row_brief(r, employee, company) for r in all_done_rows]
        people.append(person)
        cs = company_stats.setdefault(company.id, {
            "id": company.id,
            "name": company.name,
            "employee_count": 0,
            "excel_people": 0,
            "excel_lists": 0,
            "all_given": 0,
            "all_done": 0,
            "today_given": 0,
            "today_done": 0,
            "leftover": 0,
            "on_track": 0,
            "lacking": 0,
        })
        cs["excel_people"] += 1
        cs["excel_lists"] += len(emp_lists)
        cs["all_given"] += person["all_given"]
        cs["all_done"] += person["all_done"]
        cs["today_given"] += today_given
        cs["today_done"] += today_done
        cs["leftover"] += leftover
        if person["on_track"]:
            cs["on_track"] += 1
        if person["lacking"]:
            cs["lacking"] += 1

    people.sort(key=lambda p: (p["company_name"], p["employee_name"]))
    done_today = [p for p in people if p["finished_today"]]
    lacking = [p for p in people if p["lacking"]]
    on_track = [p for p in people if p["on_track"]]
    earnings = Earning.query.filter_by(earned_date=day).all()
    earnings_total = sum(float(e.amount) for e in earnings)
    completed_work = []
    open_work = []
    completed_any = []
    if include_details:
        for p in people:
            completed_work.extend(p.get("completed") or [])
            open_work.extend(p.get("open") or [])
            completed_any.extend(p.get("completed_any") or [])
    all_given = sum(p["all_given"] for p in people)
    all_done = sum(p["all_done"] for p in people)
    today_given = sum(p["today_given"] for p in people)
    today_done = sum(p["today_done"] for p in people)
    leftover = sum(p["leftover"] for p in people)
    return {
        "date": day_iso,
        "error": None,
        "summary": {
            "excel_people": len(people),
            "excel_lists": len(lists),
            "working_today": sum(1 for p in people if p["today_given"] > 0),
            "finished_today": len(done_today),
            "on_track": len(on_track),
            "lacking": len(lacking),
            "all_given": all_given,
            "all_done": all_done,
            "all_open": all_given - all_done,
            "today_given": today_given,
            "today_done": today_done,
            "today_open": today_given - today_done,
            "leftover": leftover,
            "earnings_total": round(earnings_total, 2),
            "earnings_count": len(earnings),
        },
        "on_track": on_track,
        "lacking": lacking,
        "finished_today": done_today,
        "people": people,
        "companies": list(company_stats.values()),
        "completed_work": completed_work,
        "open_work": open_work,
        "completed_any": completed_any,
    }
