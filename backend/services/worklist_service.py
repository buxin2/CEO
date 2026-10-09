"""Excel/CSV company task lists, drip-fed to employees each day."""

import csv
import io
import json
from datetime import date, datetime, timedelta

from models import db, Employee, WorkList, WorkListRow


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    text = str(value).strip()
    if text.lower() == "none":
        return ""
    return text


def _header_name(raw, index):
    name = _cell(raw)
    if not name:
        return "Column " + str(index + 1)
    return name[:120]


def parse_task_file(upload):
    filename = (upload.filename or "tasks.xlsx").strip()
    raw = upload.read()
    if not raw:
        raise ValueError("The file is empty.")
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        grid = [[_cell(c) for c in row] for row in reader]
    elif lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("Excel support is not installed on the server.") from exc
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
        grid = [[_cell(c) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raise ValueError("Upload an Excel .xlsx file or a .csv file.")

    grid = [row for row in grid if any(str(c).strip() for c in row)]
    if len(grid) < 2:
        raise ValueError("The file needs a header row and at least one task row.")

    headers = [_header_name(grid[0][i] if i < len(grid[0]) else "", i) for i in range(len(grid[0]))]
    rows = []
    number = 1
    for source in grid[1:]:
        fields = {}
        empty = True
        for i, header in enumerate(headers):
            val = source[i] if i < len(source) else ""
            fields[header] = val
            if val:
                empty = False
        if empty:
            continue
        rows.append({"row_number": number, "fields": fields})
        number += 1
    if not rows:
        raise ValueError("No task rows were found in the file.")
    return filename, headers, rows


def create_work_list(company_id, employee_id, upload, daily_quota=5):
    employee = Employee.query.filter_by(id=employee_id, company_id=company_id).first()
    if not employee:
        raise ValueError("Employee not found.")
    try:
        quota = int(daily_quota or 5)
    except (TypeError, ValueError):
        quota = 5
    quota = max(1, min(50, quota))
    filename, headers, rows = parse_task_file(upload)
    work = WorkList(
        company_id=company_id,
        employee_id=employee.id,
        filename=filename[:255],
        daily_quota=quota,
        headers_json=json.dumps(headers),
    )
    db.session.add(work)
    db.session.flush()
    for row in rows:
        db.session.add(WorkListRow(
            work_list_id=work.id,
            row_number=row["row_number"],
            data_json=json.dumps(row["fields"]),
            status="pending",
        ))
    db.session.commit()
    release_today(work)
    return work


def update_work_list(work_list_id, company_id, data):
    work = WorkList.query.filter_by(id=work_list_id, company_id=company_id).first()
    if not work:
        raise ValueError("Task list not found.")
    if data.get("daily_quota") is not None:
        try:
            work.daily_quota = max(1, min(50, int(data.get("daily_quota"))))
        except (TypeError, ValueError):
            raise ValueError("Daily tasks must be a number from 1 to 50.")
    if data.get("employee_id"):
        employee = Employee.query.filter_by(id=int(data["employee_id"]), company_id=company_id).first()
        if not employee:
            raise ValueError("Employee not found.")
        work.employee_id = employee.id
    db.session.commit()
    release_today(work)
    return work


def delete_work_list(work_list_id, company_id):
    work = WorkList.query.filter_by(id=work_list_id, company_id=company_id).first()
    if not work:
        raise ValueError("Task list not found.")
    db.session.delete(work)
    db.session.commit()


def list_work_lists(company_id, employee_id=None):
    q = WorkList.query.filter_by(company_id=company_id)
    if employee_id:
        q = q.filter_by(employee_id=employee_id)
    rows = q.order_by(WorkList.created_at.desc()).all()
    for work in rows:
        release_today(work)
    return rows


def release_today(work, today=None):
    """Give this employee up to daily_quota new Excel rows for today."""
    today = today or date.today()
    quota = max(1, int(work.daily_quota or 5))
    already = WorkListRow.query.filter_by(work_list_id=work.id, assigned_date=today).count()
    need = quota - already
    if need <= 0:
        return 0
    waiting = (
        WorkListRow.query.filter_by(work_list_id=work.id)
        .filter(WorkListRow.assigned_date.is_(None))
        .order_by(WorkListRow.row_number.asc())
        .limit(need)
        .all()
    )
    for row in waiting:
        row.assigned_date = today
    if waiting:
        db.session.commit()
    return len(waiting)


def release_for_employee(employee):
    lists = WorkList.query.filter_by(employee_id=employee.id).all()
    for work in lists:
        release_today(work)
    return lists


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _weekday_name(d):
    d = _as_date(d)
    if not d:
        return ""
    return ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[d.weekday()]


def _progress_payload(total, remaining, given, done, pending, days, daily_quota=5):
    sheet_pct = int(round(100.0 * done / total)) if total else 0
    given_pct = int(round(100.0 * done / given)) if given else 0
    return {
        "total": total,
        "remaining": remaining,
        "given": given,
        "done": done,
        "pending": pending,
        "sheet_pct": sheet_pct,
        "given_pct": given_pct,
        "daily_quota": int(daily_quota or 5),
        "days": days,
    }


def _days_from_pairs(pairs, today=None):
    today = today or date.today()
    by = {}
    for assigned, status in pairs:
        assigned = _as_date(assigned)
        if not assigned:
            continue
        item = by.setdefault(assigned, {"given": 0, "done": 0, "pending": 0})
        item["given"] += 1
        if status == "done":
            item["done"] += 1
        else:
            item["pending"] += 1
    days = []
    for d in sorted(by.keys()):
        item = by[d]
        days.append({
            "date": d.isoformat(),
            "weekday": _weekday_name(d),
            "is_today": d == today,
            "is_yesterday": d == today - timedelta(days=1),
            "given": item["given"],
            "done": item["done"],
            "pending": item["pending"],
        })
    return days


def _progress_from_assigned(lists, rows, today=None):
    today = today or date.today()
    ids = [w.id for w in lists]
    remaining = 0
    if ids:
        remaining = (
            WorkListRow.query.filter(WorkListRow.work_list_id.in_(ids))
            .filter(WorkListRow.assigned_date.is_(None))
            .count()
        )
    given = len(rows)
    done = sum(1 for r in rows if (r.status or "") == "done")
    pending = given - done
    total = remaining + given
    pairs = [(_as_date(r.assigned_date), r.status or "pending") for r in rows]
    quota = lists[0].daily_quota if lists else 5
    payload = _progress_payload(
        total, remaining, given, done, pending,
        _days_from_pairs(pairs, today=today),
        quota,
    )
    payload["previous_pending"] = sum(
        1 for r in rows
        if _as_date(r.assigned_date) and _as_date(r.assigned_date) < today and (r.status or "") != "done"
    )
    return payload


def progress_for_work(work, today=None):
    rows = (
        WorkListRow.query.filter_by(work_list_id=work.id)
        .filter(WorkListRow.assigned_date.isnot(None))
        .all()
    )
    return _progress_from_assigned([work], rows, today=today)


def progress_for_employee(employee, today=None):
    lists = WorkList.query.filter_by(employee_id=employee.id).all()
    if not lists:
        return _progress_payload(0, 0, 0, 0, 0, [], 5), lists
    ids = [w.id for w in lists]
    q = WorkListRow.query.filter(WorkListRow.work_list_id.in_(ids))
    total = q.count()
    remaining = q.filter(WorkListRow.assigned_date.is_(None)).count()
    given = total - remaining
    done = q.filter_by(status="done").count()
    pending = (
        q.filter(WorkListRow.assigned_date.isnot(None))
        .filter(WorkListRow.status != "done")
        .count()
    )
    pairs = (
        db.session.query(WorkListRow.assigned_date, WorkListRow.status)
        .filter(WorkListRow.work_list_id.in_(ids))
        .filter(WorkListRow.assigned_date.isnot(None))
        .all()
    )
    quota = lists[0].daily_quota if lists else 5
    return _progress_payload(
        total, remaining, given, done, pending,
        _days_from_pairs(pairs, today=today),
        quota,
    ), lists


def assigned_rows_for_employee(employee):
    lists = release_for_employee(employee)
    ids = [w.id for w in lists]
    if not ids:
        return [], lists, _progress_from_assigned(lists, [])
    rows = (
        WorkListRow.query.filter(WorkListRow.work_list_id.in_(ids))
        .filter(WorkListRow.assigned_date.isnot(None))
        .order_by(WorkListRow.assigned_date.desc(), WorkListRow.row_number.asc())
        .all()
    )
    return rows, lists, _progress_from_assigned(lists, rows)


def _apply_row_update(row, data):
    if row.assigned_date is None:
        raise ValueError("This task has not been given yet.")
    if "notes" in data:
        row.notes = str(data.get("notes") or "")
    if data.get("status") == "done":
        row.status = "done"
        row.completed_at = datetime.utcnow()
    elif data.get("status") == "pending":
        row.status = "pending"
        row.completed_at = None
    fields = row.fields()
    incoming = data.get("fields")
    if isinstance(incoming, dict):
        for key, val in incoming.items():
            if key in fields or key in row.work_list.headers():
                fields[str(key)[:120]] = _cell(val)
        row.data_json = json.dumps(fields)
    db.session.commit()
    return row


def update_row_for_employee(employee, row_id, data):
    row = WorkListRow.query.get(row_id)
    if not row or not row.work_list or row.work_list.employee_id != employee.id:
        raise ValueError("Task not found.")
    return _apply_row_update(row, data)


def update_row_for_company(company_id, work_list_id, row_id, data):
    row = WorkListRow.query.get(row_id)
    if (
        not row
        or not row.work_list
        or row.work_list.company_id != company_id
        or row.work_list_id != work_list_id
    ):
        raise ValueError("Task not found.")
    return _apply_row_update(row, data)
