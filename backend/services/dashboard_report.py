"""CEO dashboard: Excel work given, completed, leftover, and day reports."""

from datetime import date

from models import Company, Employee, Earning, WorkList, WorkListRow
from services.worklist_service import _as_date, release_today


def _row_brief(row, employee, company):
    return {
        "id": row.id,
        "row_number": row.row_number,
        "title": row.title(),
        "status": row.status or "pending",
        "notes": (row.notes or "").strip(),
        "assigned_date": row.assigned_date.isoformat() if row.assigned_date else None,
        "employee_id": employee.id,
        "employee_name": employee.name,
        "company_id": company.id,
        "company_name": company.name,
    }


def _person_payload(employee, company, lists, assigned_rows, day):
    today_rows = [r for r in assigned_rows if _as_date(r.assigned_date) == day]
    leftover_rows = [
        r for r in assigned_rows
        if _as_date(r.assigned_date) and _as_date(r.assigned_date) < day and (r.status or "") != "done"
    ]
    today_done_rows = [r for r in today_rows if (r.status or "") == "done"]
    today_open_rows = [r for r in today_rows if (r.status or "") != "done"]
    today_given = len(today_rows)
    today_done = len(today_done_rows)
    leftover = len(leftover_rows)
    finished_today = today_given > 0 and today_done == today_given
    lacking = leftover > 0 or (today_given > 0 and today_done < today_given)
    on_track = (not lacking) and bool(lists)
    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "company_id": company.id,
        "company_name": company.name,
        "has_excel": True,
        "today_given": today_given,
        "today_done": today_done,
        "today_open": len(today_open_rows),
        "leftover": leftover,
        "finished_today": finished_today,
        "on_track": on_track,
        "lacking": lacking,
        "completed": [_row_brief(r, employee, company) for r in today_done_rows],
        "open": [_row_brief(r, employee, company) for r in today_open_rows],
        "leftover_items": [_row_brief(r, employee, company) for r in leftover_rows],
    }


def dashboard_work_report(day=None, include_details=True):
    day = day or date.today()
    if day == date.today():
        for work in WorkList.query.all():
            release_today(work, today=day)

    people = []
    company_stats = {}
    for company in Company.query.order_by(Company.name.asc()).all():
        company_stats[company.id] = {
            "id": company.id,
            "name": company.name,
            "employee_count": company.employees.count(),
            "excel_people": 0,
            "today_given": 0,
            "today_done": 0,
            "leftover": 0,
            "on_track": 0,
            "lacking": 0,
        }
        for employee in company.employees.order_by(Employee.name.asc()).all():
            lists = WorkList.query.filter_by(employee_id=employee.id).all()
            if not lists:
                continue
            ids = [w.id for w in lists]
            assigned = (
                WorkListRow.query.filter(WorkListRow.work_list_id.in_(ids))
                .filter(WorkListRow.assigned_date.isnot(None))
                .all()
            )
            person = _person_payload(employee, company, lists, assigned, day)
            if not include_details:
                person = {k: person[k] for k in person if k not in ("completed", "open", "leftover_items")}
            people.append(person)
            cs = company_stats[company.id]
            cs["excel_people"] += 1
            cs["today_given"] += person["today_given"]
            cs["today_done"] += person["today_done"]
            cs["leftover"] += person["leftover"]
            if person["on_track"]:
                cs["on_track"] += 1
            if person["lacking"]:
                cs["lacking"] += 1

    done_today = [p for p in people if p["finished_today"]]
    lacking = [p for p in people if p["lacking"]]
    on_track = [p for p in people if p["on_track"]]
    working = [p for p in people if p["today_given"] > 0]
    given = sum(p["today_given"] for p in people)
    completed = sum(p["today_done"] for p in people)
    leftover = sum(p["leftover"] for p in people)
    earnings = Earning.query.filter_by(earned_date=day).all()
    earnings_total = sum(float(e.amount) for e in earnings)
    completed_work = []
    open_work = []
    if include_details:
        for p in people:
            completed_work.extend(p.get("completed") or [])
            open_work.extend(p.get("open") or [])
    return {
        "date": day.isoformat(),
        "summary": {
            "excel_people": len(people),
            "working_today": len(working),
            "finished_today": len(done_today),
            "on_track": len(on_track),
            "lacking": len(lacking),
            "today_given": given,
            "today_done": completed,
            "today_open": given - completed,
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
    }
