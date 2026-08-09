from datetime import datetime

from flask import Blueprint, jsonify, request, session

from models import (
    db,
    Company,
    Employee,
    Task,
    CompanyGroup,
    GroupMember,
    GroupMessage,
    GroupMessageReaction,
    GroupJoinRequest,
    get_week_bounds,
)
from routes.auth import login_required
from utils import group_link_for_token, task_link_for_token

group_bp = Blueprint("group", __name__)


def _get_group_by_token(token):
    return CompanyGroup.query.filter_by(group_token=token).first()


def _get_employee_for_group(group, employee_token):
    if not group or not employee_token:
        return None
    return Employee.query.filter_by(
        unique_token=employee_token, company_id=group.company_id
    ).first()


def _employee_token_from_request():
    return (
        request.headers.get("X-Employee-Token")
        or request.args.get("employee_token")
        or (request.get_json(silent=True) or {}).get("employee_token")
    )


def _record_group_entry(group, employee):
    member = GroupMember.query.filter_by(
        group_id=group.id, employee_id=employee.id
    ).first()
    if member:
        member.removed_at = None
        member.joined_at = datetime.utcnow()
    else:
        db.session.add(GroupMember(group_id=group.id, employee_id=employee.id))
    db.session.commit()


def _message_query(group_id, parent_id=None):
    q = GroupMessage.query.filter_by(group_id=group_id, deleted_at=None)
    if parent_id is None:
        q = q.filter(GroupMessage.parent_id.is_(None))
    else:
        q = q.filter_by(parent_id=parent_id)
    return q.order_by(GroupMessage.created_at.asc())


# ---------- Public group (token-based) ----------


@group_bp.route("/api/public/group/<token>", methods=["GET"])
def api_public_group_info(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    employees = group.company.employees.order_by(Employee.name.asc()).all()
    return jsonify({
        "company_name": group.company.name,
        "group_name": group.display_name(),
        "member_count": group.active_member_count(),
        "employees": [
            {
                "id": e.id,
                "name": e.name,
                "position": e.position or "",
                "unique_token": e.unique_token,
            }
            for e in employees
        ],
    })


@group_bp.route("/api/public/group/<token>/enter", methods=["POST"])
def api_public_group_enter(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    data = request.get_json(silent=True) or {}
    employee_token = data.get("employee_token") or ""
    employee = _get_employee_for_group(group, employee_token)
    if not employee:
        return jsonify({"error": "Please select a valid employee name."}), 400

    _record_group_entry(group, employee)
    return jsonify({
        "success": True,
        "employee": {
            "id": employee.id,
            "name": employee.name,
            "position": employee.position or "",
            "unique_token": employee.unique_token,
        },
        "group_name": group.display_name(),
        "company_name": group.company.name,
    })


@group_bp.route("/api/public/group/<token>/join-request", methods=["POST"])
def api_public_join_request(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "").strip()
    if not name:
        return jsonify({"error": "Name is required."}), 400

    req = GroupJoinRequest(group_id=group.id, name=name, role=role, status="pending")
    db.session.add(req)
    db.session.commit()
    return jsonify(req.to_dict()), 201


@group_bp.route("/api/public/group/<token>/messages", methods=["GET"])
def api_public_list_messages(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    employee_token = _employee_token_from_request()
    employee = _get_employee_for_group(group, employee_token)
    if not employee:
        return jsonify({"error": "Invalid employee session. Please enter the group again."}), 401

    after_id = request.args.get("after_id", type=int)
    parent_id = request.args.get("parent_id", type=int)

    if parent_id:
        messages = _message_query(group.id, parent_id=parent_id).all()
    else:
        q = _message_query(group.id)
        if after_id:
            q = q.filter(GroupMessage.id > after_id)
        messages = q.all()

    my_reactions = {}
    if messages:
        msg_ids = [m.id for m in messages]
        for r in GroupMessageReaction.query.filter(
            GroupMessageReaction.message_id.in_(msg_ids),
            GroupMessageReaction.employee_id == employee.id,
        ):
            my_reactions[r.message_id] = r.reaction

    return jsonify({
        "messages": [m.to_dict() for m in messages],
        "my_reactions": my_reactions,
    })


@group_bp.route("/api/public/group/<token>/messages", methods=["POST"])
def api_public_post_message(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    employee_token = _employee_token_from_request()
    employee = _get_employee_for_group(group, employee_token)
    if not employee:
        return jsonify({"error": "Invalid employee session. Please enter the group again."}), 401

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    parent_id = data.get("parent_id")

    if not content:
        return jsonify({"error": "Message cannot be empty."}), 400

    if parent_id:
        parent = GroupMessage.query.filter_by(
            id=parent_id, group_id=group.id, deleted_at=None
        ).first()
        if not parent:
            return jsonify({"error": "Parent message not found."}), 404

    member = GroupMember.query.filter_by(
        group_id=group.id, employee_id=employee.id, removed_at=None
    ).first()
    if not member:
        _record_group_entry(group, employee)

    msg = GroupMessage(
        group_id=group.id,
        employee_id=employee.id,
        parent_id=parent_id,
        content=content,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@group_bp.route("/api/public/group/<token>/messages/<int:message_id>/react", methods=["POST"])
def api_public_react_message(token, message_id):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    employee_token = _employee_token_from_request()
    employee = _get_employee_for_group(group, employee_token)
    if not employee:
        return jsonify({"error": "Invalid employee session."}), 401

    msg = GroupMessage.query.filter_by(
        id=message_id, group_id=group.id, deleted_at=None
    ).first()
    if not msg:
        return jsonify({"error": "Message not found."}), 404

    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")

    existing = GroupMessageReaction.query.filter_by(
        message_id=message_id, employee_id=employee.id
    ).first()

    if reaction not in ("like", "dislike"):
        if existing:
            db.session.delete(existing)
    elif existing:
        existing.reaction = reaction
    else:
        db.session.add(
            GroupMessageReaction(
                message_id=message_id, employee_id=employee.id, reaction=reaction
            )
        )

    db.session.commit()
    msg = GroupMessage.query.get(message_id)
    return jsonify(msg.to_dict())


@group_bp.route("/api/public/group/<token>/members", methods=["GET"])
def api_public_group_members(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    members = (
        GroupMember.query.filter_by(group_id=group.id)
        .filter(GroupMember.removed_at.is_(None))
        .all()
    )
    result = []
    for m in members:
        e = m.employee
        if e:
            result.append({
                "employee_id": e.id,
                "name": e.name,
                "position": e.position or "Team member",
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            })
    result.sort(key=lambda x: x["name"].lower())
    return jsonify({"members": result, "count": len(result)})


@group_bp.route("/api/public/group/<token>/my-tasks", methods=["GET"])
def api_public_group_my_tasks(token):
    group = _get_group_by_token(token)
    if not group:
        return jsonify({"error": "This group link is invalid or no longer available."}), 404

    employee_token = _employee_token_from_request()
    employee = _get_employee_for_group(group, employee_token)
    if not employee:
        return jsonify({"error": "Invalid employee session."}), 401

    week_start, week_end = get_week_bounds()
    tasks = (
        employee.tasks.filter(Task.week_start == week_start, Task.week_end == week_end)
        .order_by(Task.created_at.asc())
        .all()
    )
    stats = employee.get_week_stats(week_start, week_end)

    return jsonify({
        "employee_name": employee.name,
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
        "tasks": [t.to_dict() for t in tasks],
        "stats": stats,
    })


# ---------- Admin group management ----------


@group_bp.route("/api/companies/<int:company_id>/group", methods=["GET"])
@login_required
def api_admin_get_group(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found."}), 404

    group = company.group
    if not group:
        from utils import create_group_for_company

        group = create_group_for_company(company)
        db.session.add(group)
        db.session.commit()

    data = group.to_dict(include_link=True)
    data["group_link"] = group_link_for_token(group.group_token)
    data["pending_requests"] = GroupJoinRequest.query.filter_by(
        group_id=group.id, status="pending"
    ).count()
    return jsonify(data)


@group_bp.route("/api/companies/<int:company_id>/group/messages", methods=["GET"])
@login_required
def api_admin_list_messages(company_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    group = company.group
    after_id = request.args.get("after_id", type=int)
    parent_id = request.args.get("parent_id", type=int)

    if parent_id:
        messages = _message_query(group.id, parent_id=parent_id).all()
    else:
        q = _message_query(group.id)
        if after_id:
            q = q.filter(GroupMessage.id > after_id)
        messages = q.all()

    return jsonify({"messages": [m.to_dict() for m in messages]})


@group_bp.route("/api/companies/<int:company_id>/group/messages", methods=["POST"])
@login_required
def api_admin_post_message(company_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    group = company.group
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    parent_id = data.get("parent_id")

    if not content:
        return jsonify({"error": "Message cannot be empty."}), 400

    if parent_id:
        parent = GroupMessage.query.filter_by(
            id=parent_id, group_id=group.id, deleted_at=None
        ).first()
        if not parent:
            return jsonify({"error": "Parent message not found."}), 404

    msg = GroupMessage(
        group_id=group.id,
        admin_id=session.get("admin_id"),
        parent_id=parent_id,
        content=content,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@group_bp.route("/api/group/messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_admin_delete_message(message_id):
    msg = GroupMessage.query.get(message_id)
    if not msg or msg.deleted_at:
        return jsonify({"error": "Message not found."}), 404

    msg.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})


@group_bp.route("/api/companies/<int:company_id>/group/members/<int:employee_id>", methods=["DELETE"])
@login_required
def api_admin_remove_member(company_id, employee_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    member = GroupMember.query.filter_by(
        group_id=company.group.id, employee_id=employee_id
    ).first()
    if not member:
        return jsonify({"error": "Member not found in group."}), 404

    member.removed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})


@group_bp.route("/api/companies/<int:company_id>/group/members", methods=["GET"])
@login_required
def api_admin_group_members(company_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    members = (
        GroupMember.query.filter_by(group_id=company.group.id)
        .filter(GroupMember.removed_at.is_(None))
        .all()
    )
    result = []
    for m in members:
        e = m.employee
        if e:
            result.append({
                "employee_id": e.id,
                "name": e.name,
                "position": e.position or "Team member",
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            })
    result.sort(key=lambda x: x["name"].lower())
    return jsonify({"members": result, "count": len(result)})


@group_bp.route("/api/companies/<int:company_id>/group/join-requests", methods=["GET"])
@login_required
def api_admin_join_requests(company_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    pending = (
        GroupJoinRequest.query.filter_by(group_id=company.group.id, status="pending")
        .order_by(GroupJoinRequest.created_at.asc())
        .all()
    )
    return jsonify([r.to_dict() for r in pending])


@group_bp.route("/api/companies/<int:company_id>/group/join-requests/<int:request_id>/approve", methods=["POST"])
@login_required
def api_admin_approve_join_request(company_id, request_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    req = GroupJoinRequest.query.filter_by(
        id=request_id, group_id=company.group.id, status="pending"
    ).first()
    if not req:
        return jsonify({"error": "Join request not found."}), 404

    employee = Employee(
        company_id=company.id,
        name=req.name,
        position=req.role,
    )
    db.session.add(employee)
    db.session.flush()

    db.session.add(GroupMember(group_id=company.group.id, employee_id=employee.id))
    req.status = "approved"
    db.session.commit()

    result = employee.to_dict()
    result["task_link"] = task_link_for_token(employee.unique_token)
    return jsonify({"success": True, "employee": result})


@group_bp.route("/api/companies/<int:company_id>/group/join-requests/<int:request_id>/reject", methods=["POST"])
@login_required
def api_admin_reject_join_request(company_id, request_id):
    company = Company.query.get(company_id)
    if not company or not company.group:
        return jsonify({"error": "Company or group not found."}), 404

    req = GroupJoinRequest.query.filter_by(
        id=request_id, group_id=company.group.id, status="pending"
    ).first()
    if not req:
        return jsonify({"error": "Join request not found."}), 404

    req.status = "rejected"
    db.session.commit()
    return jsonify({"success": True})
