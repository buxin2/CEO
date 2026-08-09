from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from models import db, Employee, Task, get_week_bounds
from routes.auth import login_required
from utils import task_link_for_token

employee_bp = Blueprint("employee", __name__)


def _parse_week_param():
    week_start_str = request.args.get("week_start")
    if week_start_str:
        try:
            ref = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            return get_week_bounds(ref)
        except ValueError:
            pass
    return get_week_bounds()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@employee_bp.route("/api/employees/<int:employee_id>", methods=["GET"])
@login_required
def api_get_employee(employee_id):
    week_start, week_end = _parse_week_param()
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    result = employee.to_dict(include_stats=True, week_start=week_start, week_end=week_end)
    result["company_name"] = employee.company.name
    result["task_link"] = task_link_for_token(employee.unique_token)
    return jsonify(result)


@employee_bp.route("/api/employees/<int:employee_id>", methods=["PUT"])
@login_required
def api_update_employee(employee_id):
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    position = data.get("position")

    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "Employee name cannot be empty."}), 400
        employee.name = name
    if email is not None:
        employee.email = email.strip()
    if position is not None:
        employee.position = position.strip()

    db.session.commit()
    return jsonify(employee.to_dict())


@employee_bp.route("/api/employees/<int:employee_id>", methods=["DELETE"])
@login_required
def api_delete_employee(employee_id):
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    db.session.delete(employee)
    db.session.commit()
    return jsonify({"success": True})


@employee_bp.route("/api/employees/<int:employee_id>/tasks", methods=["GET"])
@login_required
def api_list_employee_tasks(employee_id):
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    week_start, week_end = _parse_week_param()

    status_filter = (request.args.get("status") or "all").lower()
    priority_filter = (request.args.get("priority") or "all").lower()

    query = employee.tasks.filter(Task.week_start == week_start, Task.week_end == week_end)

    if status_filter in ("pending", "completed"):
        query = query.filter(Task.status == status_filter)
    if priority_filter in ("low", "medium", "high"):
        query = query.filter(Task.priority == priority_filter)

    tasks = query.order_by(Task.created_at.asc()).all()

    return jsonify({
        "tasks": [t.to_dict() for t in tasks],
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "prev_week_start": (week_start - timedelta(days=7)).isoformat(),
            "next_week_start": (week_start + timedelta(days=7)).isoformat(),
        },
        "stats": employee.get_week_stats(week_start, week_end),
    })


@employee_bp.route("/api/employees/<int:employee_id>/tasks", methods=["POST"])
@login_required
def api_create_task(employee_id):
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    priority = (data.get("priority") or "medium").strip().lower()
    due_date = _parse_date(data.get("due_date"))

    if not title:
        return jsonify({"error": "Task title is required."}), 400
    if priority not in ("low", "medium", "high"):
        priority = "medium"

    week_start_param = data.get("week_start")
    if week_start_param:
        ref = _parse_date(week_start_param)
        week_start, week_end = get_week_bounds(ref) if ref else get_week_bounds()
    else:
        week_start, week_end = get_week_bounds()

    task = Task(
        employee_id=employee.id,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        week_start=week_start,
        week_end=week_end,
        status="pending",
    )
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@employee_bp.route("/api/employees/<int:employee_id>/copy-last-week", methods=["POST"])
@login_required
def api_copy_last_week(employee_id):
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404

    data = request.get_json(silent=True) or {}
    week_start_param = data.get("week_start")
    if week_start_param:
        ref = _parse_date(week_start_param)
        current_week_start, current_week_end = get_week_bounds(ref) if ref else get_week_bounds()
    else:
        current_week_start, current_week_end = get_week_bounds()

    last_week_start = current_week_start - timedelta(days=7)
    last_week_end = current_week_end - timedelta(days=7)

    last_week_tasks = employee.tasks.filter(
        Task.week_start == last_week_start, Task.week_end == last_week_end
    ).all()

    if not last_week_tasks:
        return jsonify({"error": "No tasks found for last week."}), 404

    created = []
    for t in last_week_tasks:
        new_task = Task(
            employee_id=employee.id,
            title=t.title,
            description=t.description,
            priority=t.priority,
            due_date=t.due_date,
            week_start=current_week_start,
            week_end=current_week_end,
            status="pending",
        )
        db.session.add(new_task)
        created.append(new_task)

    db.session.commit()
    return jsonify({"success": True, "created": [t.to_dict() for t in created]}), 201


@employee_bp.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def api_update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    description = data.get("description")
    priority = data.get("priority")
    due_date = data.get("due_date")

    if title is not None:
        title = title.strip()
        if not title:
            return jsonify({"error": "Task title cannot be empty."}), 400
        task.title = title
    if description is not None:
        task.description = description.strip()
    if priority is not None and priority.lower() in ("low", "medium", "high"):
        task.priority = priority.lower()
    if due_date is not None:
        task.due_date = _parse_date(due_date)

    db.session.commit()
    return jsonify(task.to_dict())


@employee_bp.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def api_delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True})


@employee_bp.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def api_complete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    task.status = "completed"
    task.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())


@employee_bp.route("/api/tasks/<int:task_id>/uncomplete", methods=["POST"])
@login_required
def api_uncomplete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    task.status = "pending"
    task.completed_at = None
    db.session.commit()
    return jsonify(task.to_dict())
