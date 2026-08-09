from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from models import db, get_week_bounds
from routes.auth import login_required
from services.planner_snapshot import build_planner_snapshot, period_keys_for
from services.planner_service import (
    get_planner_settings,
    list_goals,
    create_goal,
    update_goal,
    delete_goal,
    list_timetable_for_date,
    list_timetable_range,
    timetable_progress,
    create_timetable_item,
    update_timetable_item,
    delete_timetable_item,
    reset_timetable_for_date,
    serialize_item,
    daily_summary,
)
from services.planner_ai import generate_timetable_with_ai, suggest_next_activity

planner_bp = Blueprint("planner", __name__)


def _parse_date(value, default=None):
    if not value:
        return default or date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default or date.today()


@planner_bp.route("/api/planner/snapshot", methods=["GET"])
@login_required
def api_planner_snapshot():
    ref = _parse_date(request.args.get("date"))
    return jsonify(build_planner_snapshot(ref))


@planner_bp.route("/api/planner/settings", methods=["GET"])
@login_required
def api_get_settings():
    s = get_planner_settings()
    return jsonify({
        "personal_notes": s.personal_notes or "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    })


@planner_bp.route("/api/planner/settings", methods=["PUT"])
@login_required
def api_update_settings():
    data = request.get_json(silent=True) or {}
    s = get_planner_settings()
    if data.get("personal_notes") is not None:
        s.personal_notes = data["personal_notes"].strip()
    db.session.commit()
    return jsonify({"personal_notes": s.personal_notes})


@planner_bp.route("/api/planner/goals", methods=["GET"])
@login_required
def api_list_goals():
    scope = (request.args.get("scope") or "daily").lower()
    period_key = request.args.get("period_key")
    if not period_key:
        keys = period_keys_for(_parse_date(request.args.get("date")))
        period_key = keys.get(scope, keys["daily"])
    goals = list_goals(scope, period_key)
    return jsonify({
        "scope": scope,
        "period_key": period_key,
        "goals": [g.to_dict() for g in goals],
    })


@planner_bp.route("/api/planner/goals", methods=["POST"])
@login_required
def api_create_goal():
    data = request.get_json(silent=True) or {}
    scope = (data.get("scope") or "daily").lower()
    period_key = data.get("period_key")
    if not period_key:
        keys = period_keys_for(_parse_date(data.get("date")))
        period_key = keys.get(scope, keys["daily"])
    try:
        goal = create_goal(scope, period_key, data.get("title"))
        return jsonify(goal.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/goals/<int:goal_id>", methods=["PUT"])
@login_required
def api_update_goal(goal_id):
    data = request.get_json(silent=True) or {}
    try:
        goal = update_goal(goal_id, **data)
        return jsonify(goal.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/goals/<int:goal_id>", methods=["DELETE"])
@login_required
def api_delete_goal(goal_id):
    try:
        delete_goal(goal_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/timetable", methods=["GET"])
@login_required
def api_get_timetable():
    view = (request.args.get("view") or "day").lower()
    ref = _parse_date(request.args.get("date"))

    if view == "week":
        week_start, week_end = get_week_bounds(ref)
        items = list_timetable_range(week_start, week_end)
        by_day = {}
        for item in items:
            key = item.plan_date.isoformat()
            by_day.setdefault(key, []).append(serialize_item(item))
        return jsonify({
            "view": "week",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "days": by_day,
        })

    items = list_timetable_for_date(ref)
    prog = timetable_progress(items)
    keys = period_keys_for(ref)
    return jsonify({
        "view": "day",
        "date": ref.isoformat(),
        "period_keys": keys,
        "items": [serialize_item(i) for i in items],
        "progress": prog,
        "summary": daily_summary(ref),
    })


@planner_bp.route("/api/planner/timetable", methods=["POST"])
@login_required
def api_create_timetable_item():
    data = request.get_json(silent=True) or {}
    plan_date = _parse_date(data.get("plan_date"))
    try:
        item = create_timetable_item(plan_date, data)
        return jsonify(serialize_item(item)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/timetable/<int:item_id>", methods=["PUT"])
@login_required
def api_update_timetable_item(item_id):
    data = request.get_json(silent=True) or {}
    try:
        item = update_timetable_item(item_id, data)
        return jsonify(serialize_item(item))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/timetable/<int:item_id>", methods=["DELETE"])
@login_required
def api_delete_timetable_item(item_id):
    try:
        delete_timetable_item(item_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@planner_bp.route("/api/planner/timetable/reset", methods=["POST"])
@login_required
def api_reset_timetable():
    data = request.get_json(silent=True) or {}
    plan_date = _parse_date(data.get("date"))
    if not data.get("confirmed"):
        return jsonify({
            "needs_confirmation": True,
            "message": "This will delete all timetable items for this day.",
        }), 200
    reset_timetable_for_date(plan_date)
    return jsonify({"success": True, "date": plan_date.isoformat()})


@planner_bp.route("/api/planner/generate", methods=["POST"])
@login_required
def api_generate_timetable():
    if not current_app.config.get("GROQ_API_KEY"):
        return jsonify({"error": "GROQ_API_KEY is not configured."}), 503

    data = request.get_json(silent=True) or {}
    plan_date = _parse_date(data.get("date"))
    replace = bool(data.get("replace"))
    instructions = (data.get("instructions") or "").strip()

    if replace and not data.get("confirmed"):
        return jsonify({
            "needs_confirmation": True,
            "message": "Replace will clear existing items for this day before generating.",
        }), 200

    try:
        result = generate_timetable_with_ai(plan_date, replace_existing=replace, extra_instructions=instructions)
        items = list_timetable_for_date(plan_date)
        result["progress"] = timetable_progress(items)
        result["items"] = [serialize_item(i) for i in items]
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@planner_bp.route("/api/planner/what-next", methods=["POST"])
@login_required
def api_what_next():
    if not current_app.config.get("GROQ_API_KEY"):
        return jsonify({"error": "GROQ_API_KEY is not configured."}), 503

    data = request.get_json(silent=True) or {}
    plan_date = _parse_date(data.get("date"))
    current_time = data.get("current_time")
    try:
        suggestion = suggest_next_activity(plan_date, current_time)
        return jsonify({"suggestion": suggestion, "date": plan_date.isoformat()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@planner_bp.route("/api/planner/dashboard", methods=["GET"])
@login_required
def api_planner_dashboard():
    """Combined payload for timetable page."""
    ref = _parse_date(request.args.get("date"))
    tomorrow = ref + timedelta(days=1)
    keys = period_keys_for(ref)

    def goals_for(scope, pk):
        return [g.to_dict() for g in list_goals(scope, pk)]

    today_items = list_timetable_for_date(ref)
    settings = get_planner_settings()
    snap = build_planner_snapshot(ref)

    return jsonify({
        "date": ref.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "period_keys": keys,
        "personal_notes": settings.personal_notes or "",
        "goals": {
            "monthly": goals_for("monthly", keys["monthly"]),
            "weekly": goals_for("weekly", keys["weekly"]),
            "daily": goals_for("daily", keys["daily"]),
        },
        "timetable": {
            "items": [serialize_item(i) for i in today_items],
            "progress": timetable_progress(today_items),
            "summary": daily_summary(ref),
        },
        "snapshot_summary": {
            "companies": len(snap["companies"]),
            "pending_tasks": snap["totals"]["pending_tasks_this_week"],
        },
    })
