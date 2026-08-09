"""Daily Opportunity Intelligence Center API."""

from flask import Blueprint, current_app, jsonify, request, session

from routes.auth import login_required
from services.app_time import app_today, parse_date_iso
from services.opportunity_ventures import OPPORTUNITY_TYPES, VENTURES
from services.opportunity_service import (
    add_opportunity_to_timetable,
    ensure_today_report,
    generation_status,
    generate_daily_report,
    get_report_for_date,
    list_report_dates,
    list_saved_opportunities,
    news_chat,
    serialize_report,
    set_opportunity_state,
    trigger_generate_async,
)

news_bp = Blueprint("news", __name__)


@news_bp.route("/api/news/meta", methods=["GET"])
@login_required
def api_news_meta():
    return jsonify({
        "ventures": [
            {"key": v["key"], "label": v["label"], "emoji": v["emoji"]} for v in VENTURES
        ],
        "opportunity_types": [
            {"key": k, "label": v["label"], "emoji": v["emoji"]}
            for k, v in OPPORTUNITY_TYPES.items()
        ],
        "priorities": ["high", "medium", "low"],
    })


@news_bp.route("/api/news/status", methods=["GET"])
@login_required
def api_news_status():
    admin_id = session.get("admin_id")
    ensure_today_report(admin_id=admin_id)
    return jsonify(generation_status())


@news_bp.route("/api/news/dates", methods=["GET"])
@login_required
def api_news_dates():
    return jsonify({"dates": list_report_dates()})


@news_bp.route("/api/news/report", methods=["GET"])
@login_required
def api_news_report():
    admin_id = session.get("admin_id")
    date_str = request.args.get("date") or app_today().isoformat()
    report_date = parse_date_iso(date_str)
    if not report_date:
        return jsonify({"error": "Invalid date."}), 400

    venture = request.args.get("venture") or "all"
    opp_type = request.args.get("type") or "all"
    priority = request.args.get("priority") or "all"

    report = get_report_for_date(report_date)
    if not report:
        if report_date == app_today():
            ensure_today_report(admin_id=admin_id)
            report = get_report_for_date(report_date)
        if not report:
            return jsonify({
                "report_date": date_str,
                "status": "pending",
                "opportunities": [],
                "summary": {},
            })

    if report.status != "complete" and report_date == app_today():
        ensure_today_report(admin_id=admin_id)
        report = get_report_for_date(report_date)

    return jsonify(
        serialize_report(report, admin_id=admin_id, venture=venture, opp_type=opp_type, priority=priority)
    )


@news_bp.route("/api/news/generate", methods=["POST"])
@login_required
def api_news_generate():
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    date_str = data.get("date")
    report_date = parse_date_iso(date_str) if date_str else app_today()
    async_mode = bool(data.get("async", True))
    force = bool(data.get("force", True))

    if async_mode:
        trigger_generate_async(report_date, admin_id=admin_id, force=force)
        return jsonify({"success": True, "status": "generating", "report_date": report_date.isoformat()})

    try:
        report = generate_daily_report(report_date, admin_id=admin_id, force=force)
        return jsonify(serialize_report(report, admin_id=admin_id))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@news_bp.route("/api/news/cron", methods=["POST"])
def api_news_cron():
    secret = (current_app.config.get("NEWS_CRON_SECRET") or "").strip()
    if not secret:
        return jsonify({"error": "Cron not configured."}), 503
    provided = request.headers.get("X-Cron-Secret") or (request.get_json(silent=True) or {}).get("secret")
    if provided != secret:
        return jsonify({"error": "Unauthorized."}), 401

    trigger_generate_async()
    return jsonify({"success": True, "status": "generating"})


@news_bp.route("/api/news/saved", methods=["GET"])
@login_required
def api_news_saved():
    admin_id = session.get("admin_id")
    return jsonify({"opportunities": list_saved_opportunities(admin_id)})


@news_bp.route("/api/news/opportunities/<int:opportunity_id>/state", methods=["PUT"])
@login_required
def api_news_opportunity_state(opportunity_id):
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    try:
        item = set_opportunity_state(opportunity_id, admin_id, status)
        return jsonify(item)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@news_bp.route("/api/news/opportunities/<int:opportunity_id>/timetable", methods=["POST"])
@login_required
def api_news_opportunity_timetable(opportunity_id):
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    try:
        item = add_opportunity_to_timetable(
            opportunity_id,
            admin_id,
            plan_date=data.get("plan_date"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )
        return jsonify(item.to_dict(include_link=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@news_bp.route("/api/news/chat", methods=["POST"])
@login_required
def api_news_chat():
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    do_search = bool(data.get("search", False))
    try:
        reply = news_chat(message, admin_id, do_search=do_search)
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
