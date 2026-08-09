from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db, Employee, Task, get_week_bounds

public_bp = Blueprint("public", __name__)


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

    return jsonify({
        "employee_name": employee.name,
        "company_name": employee.company.name,
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
        "tasks": [t.to_dict() for t in tasks],
        "stats": stats,
    })


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
