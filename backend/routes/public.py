from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from models import db, Employee, Task, Earning, get_week_bounds
from utils import group_link_for_token, create_group_for_company

public_bp = Blueprint("public", __name__)


def _parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None, "Amount must be a valid number."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    return amount, None


@public_bp.route("/api/public/tasks/<token>", methods=["GET"])
def api_get_public_tasks(token):
    employee = Employee.query.filter_by(unique_token=token).first()
    if not employee:
        return jsonify({"error": "This task link is invalid or no longer available."}), 404

    week_start, week_end = get_week_bounds()

    tasks = (
        employee.tasks.filter(Task.week_start == week_start, Task.week_end == week_end)
        .order_by(Task.created_at.asc())
        .all()
    )

    stats = employee.get_week_stats(week_start, week_end)

    group = employee.company.group
    if not group:
        group = create_group_for_company(employee.company)
        db.session.add(group)
        db.session.commit()

    today_earnings = (
        Earning.query.filter_by(employee_id=employee.id, earned_date=date.today())
        .order_by(Earning.created_at.asc())
        .all()
    )
    today_total = sum(float(e.amount) for e in today_earnings)

    return jsonify({
        "employee_name": employee.name,
        "company_name": employee.company.name,
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
        "tasks": [t.to_dict() for t in tasks],
        "stats": stats,
        "group_link": group_link_for_token(group.group_token),
        "earnings_today": {
            "total": today_total,
            "records": [e.to_dict() for e in today_earnings],
        },
    })


@public_bp.route("/api/public/tasks/<token>/earnings", methods=["POST"])
def api_public_submit_earning(token):
    employee = Employee.query.filter_by(unique_token=token).first()
    if not employee:
        return jsonify({"error": "This task link is invalid or no longer available."}), 404

    data = request.get_json(silent=True) or {}
    amount, err = _parse_amount(data.get("amount"))
    if err:
        return jsonify({"error": err}), 400

    note = (data.get("note") or "").strip()
    earning = Earning(
        company_id=employee.company_id,
        employee_id=employee.id,
        amount=amount,
        earned_date=date.today(),
        note=note,
    )
    db.session.add(earning)
    db.session.commit()

    return jsonify(earning.to_dict(include_employee=True)), 201


@public_bp.route("/api/public/tasks/<token>/<int:task_id>/complete", methods=["POST"])
def api_public_complete_task(token, task_id):
    employee = Employee.query.filter_by(unique_token=token).first()
    if not employee:
        return jsonify({"error": "This task link is invalid or no longer available."}), 404

    task = Task.query.filter_by(id=task_id, employee_id=employee.id).first()
    if not task:
        return jsonify({"error": "Task not found."}), 404

    task.status = "completed"
    task.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())


@public_bp.route("/api/public/tasks/<token>/<int:task_id>/uncomplete", methods=["POST"])
def api_public_uncomplete_task(token, task_id):
    employee = Employee.query.filter_by(unique_token=token).first()
    if not employee:
        return jsonify({"error": "This task link is invalid or no longer available."}), 404

    task = Task.query.filter_by(id=task_id, employee_id=employee.id).first()
    if not task:
        return jsonify({"error": "Task not found."}), 404

    task.status = "pending"
    task.completed_at = None
    db.session.commit()
    return jsonify(task.to_dict())
