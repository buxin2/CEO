from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db, Company, Employee, WorkListRow, get_week_bounds, GroupJoinRequest
from routes.auth import login_required
from services.worklist_service import (
    create_work_list,
    delete_work_list,
    list_work_lists,
    progress_for_work,
    update_row_for_company,
    update_work_list,
)
from utils import task_link_for_token, create_group_for_company, group_link_for_token

company_bp = Blueprint("company", __name__)


def _parse_week_param():
    week_start_str = request.args.get("week_start")
    if week_start_str:
        try:
            ref = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            return get_week_bounds(ref)
        except ValueError:
            pass
    return get_week_bounds()


@company_bp.route("/api/companies", methods=["GET"])
@login_required
def api_list_companies():
    week_start, week_end = _parse_week_param()
    companies = Company.query.order_by(Company.name.asc()).all()
    return jsonify([c.to_dict(include_stats=True, week_start=week_start, week_end=week_end) for c in companies])


@company_bp.route("/api/companies", methods=["POST"])
@login_required
def api_create_company():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"error": "Company name is required."}), 400

    company = Company(name=name, description=description)
    db.session.add(company)
    db.session.flush()
    group = create_group_for_company(company)
    db.session.add(group)
    db.session.commit()

    result = company.to_dict()
    result["group"] = {
        "group_link": group_link_for_token(group.group_token),
        "group_name": group.display_name(),
    }
    return jsonify(result), 201


@company_bp.route("/api/companies/<int:company_id>", methods=["GET"])
@login_required
def api_get_company(company_id):
    week_start, week_end = _parse_week_param()
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404

    employees = company.employees.order_by(Employee.name.asc()).all()
    employee_search = (request.args.get("search") or "").strip().lower()
    if employee_search:
        employees = [e for e in employees if employee_search in e.name.lower()]

    return jsonify({
        "company": company.to_dict(include_stats=True, week_start=week_start, week_end=week_end),
        "employees": [
            e.to_dict(include_stats=True, week_start=week_start, week_end=week_end) for e in employees
        ],
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
        "group": _group_summary(company),
    })


def _group_summary(company):
    group = company.group
    if not group:
        group = create_group_for_company(company)
        db.session.add(group)
        db.session.commit()
    try:
        pending = GroupJoinRequest.query.filter_by(
            group_id=group.id, status="pending"
        ).count()
    except Exception:
        pending = 0

    return {
        "group_name": group.display_name(),
        "member_count": group.active_member_count(),
        "group_link": group_link_for_token(group.group_token),
        "group_token": group.group_token,
        "pending_requests": pending,
    }


@company_bp.route("/api/companies/<int:company_id>", methods=["PUT"])
@login_required
def api_update_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    description = data.get("description")

    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "Company name cannot be empty."}), 400
        company.name = name
    if description is not None:
        company.description = description.strip()

    db.session.commit()
    return jsonify(company.to_dict())


@company_bp.route("/api/companies/<int:company_id>", methods=["DELETE"])
@login_required
def api_delete_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404

    db.session.delete(company)
    db.session.commit()
    return jsonify({"success": True})


@company_bp.route("/api/companies/<int:company_id>/employees", methods=["POST"])
@login_required
def api_create_employee(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    position = (data.get("position") or "").strip()

    if not name:
        return jsonify({"error": "Employee name is required."}), 400

    employee = Employee(company_id=company.id, name=name, email=email, position=position)
    db.session.add(employee)
    db.session.commit()

    result = employee.to_dict()
    result["task_link"] = task_link_for_token(employee.unique_token)
    return jsonify(result), 201


@company_bp.route("/api/companies/<int:company_id>/work-lists", methods=["GET"])
@login_required
def api_list_work_lists(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404
    employee_id = request.args.get("employee_id", type=int)
    rows = list_work_lists(company_id, employee_id=employee_id)
    payload = []
    for w in rows:
        item = w.to_dict()
        item["progress"] = progress_for_work(w)
        payload.append(item)
    return jsonify({"work_lists": payload})


@company_bp.route("/api/companies/<int:company_id>/work-lists", methods=["POST"])
@login_required
def api_upload_work_list(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404
    upload = request.files.get("file") or request.files.get("excel")
    if not upload or not upload.filename:
        return jsonify({"error": "Upload an Excel or CSV file."}), 400
    try:
        employee_id = int(request.form.get("employee_id") or 0)
        work = create_work_list(
            company_id,
            employee_id,
            upload,
            daily_quota=request.form.get("daily_quota") or 5,
        )
        return jsonify(work.to_dict()), 201
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@company_bp.route("/api/work-lists/<int:work_list_id>", methods=["PUT"])
@login_required
def api_update_work_list(work_list_id):
    data = request.get_json(silent=True) or {}
    company_id = data.get("company_id")
    work = None
    from models import WorkList
    work = WorkList.query.get(work_list_id)
    if not work:
        return jsonify({"error": "Task list not found."}), 404
    try:
        updated = update_work_list(work_list_id, work.company_id, data)
        return jsonify(updated.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@company_bp.route("/api/work-lists/<int:work_list_id>", methods=["DELETE"])
@login_required
def api_delete_work_list(work_list_id):
    from models import WorkList
    work = WorkList.query.get(work_list_id)
    if not work:
        return jsonify({"error": "Task list not found."}), 404
    try:
        delete_work_list(work_list_id, work.company_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@company_bp.route("/api/work-lists/<int:work_list_id>/rows", methods=["GET"])
@login_required
def api_work_list_rows(work_list_id):
    from models import WorkList
    from services.worklist_service import release_today
    work = WorkList.query.get(work_list_id)
    if not work:
        return jsonify({"error": "Task list not found."}), 404
    release_today(work)
    q = WorkListRow.query.filter_by(work_list_id=work.id).order_by(
        WorkListRow.assigned_date.desc(), WorkListRow.row_number.asc()
    )
    status = (request.args.get("status") or "").strip().lower()
    day = (request.args.get("date") or "").strip()
    if status == "waiting":
        q = q.filter(WorkListRow.assigned_date.is_(None))
    else:
        q = q.filter(WorkListRow.assigned_date.isnot(None))
        if status == "today":
            from datetime import date as date_cls
            q = q.filter_by(assigned_date=date_cls.today())
        elif day:
            from datetime import date as date_cls
            try:
                q = q.filter_by(assigned_date=date_cls.fromisoformat(day))
            except ValueError:
                return jsonify({"error": "Date must be YYYY-MM-DD."}), 400
        if status in ("pending", "done"):
            q = q.filter_by(status=status)
    item = work.to_dict()
    item["progress"] = progress_for_work(work)
    return jsonify({"work_list": item, "rows": [r.to_dict() for r in q.all()]})


@company_bp.route("/api/work-lists/<int:work_list_id>/rows/<int:row_id>", methods=["PUT"])
@login_required
def api_update_work_row(work_list_id, row_id):
    from models import WorkList
    work = WorkList.query.get(work_list_id)
    if not work:
        return jsonify({"error": "Task list not found."}), 404
    data = request.get_json(silent=True) or {}
    try:
        row = update_row_for_company(work.company_id, work_list_id, row_id, data)
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
