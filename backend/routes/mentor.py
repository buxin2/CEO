"""Mentor — personal AI advisor API."""

from datetime import datetime

from flask import Blueprint, jsonify, request, session

from routes.auth import login_required
from services.groq_key_service import is_groq_configured
from services.mentor_ai import (
    mentor_advice,
    mentor_chat,
    mentor_daily_review,
    mentor_what_now,
    parse_reminder_from_message,
)
from services.mentor_service import (
    build_dashboard,
    create_problem,
    get_mentor_settings,
    list_messages,
    respond_checkin,
    update_mentor_settings,
    update_problem,
    create_checkin,
)
from services.ai_transcribe import transcribe_audio

mentor_bp = Blueprint("mentor", __name__)


@mentor_bp.route("/api/mentor/dashboard", methods=["GET"])
@login_required
def api_mentor_dashboard():
    admin_id = session.get("admin_id")
    data = build_dashboard(admin_id)
    advice = ""
    if is_groq_configured():
        try:
            advice = mentor_advice(admin_id)
        except Exception:
            advice = ""
    data["advice"] = advice
    return jsonify(data)


@mentor_bp.route("/api/mentor/settings", methods=["GET"])
@login_required
def api_mentor_settings_get():
    s = get_mentor_settings(session.get("admin_id"))
    return jsonify(s.to_dict())


@mentor_bp.route("/api/mentor/settings", methods=["PUT"])
@login_required
def api_mentor_settings_put():
    data = request.get_json(silent=True) or {}
    s = update_mentor_settings(session.get("admin_id"), data)
    return jsonify(s.to_dict())


@mentor_bp.route("/api/mentor/messages", methods=["GET"])
@login_required
def api_mentor_messages():
    rows = list_messages(session.get("admin_id"), limit=50)
    return jsonify({"messages": [m.to_dict() for m in rows]})


@mentor_bp.route("/api/mentor/chat", methods=["POST"])
@login_required
def api_mentor_chat():
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured. Add a Groq API key in Admin → AI."}), 503

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    admin_id = session.get("admin_id")

    when = parse_reminder_from_message(message)
    if when and "remind" in message.lower():
        create_checkin(admin_id, message, when, title="Reminder")
        reply = mentor_chat(admin_id, message)
    else:
        try:
            reply = mentor_chat(admin_id, message)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return jsonify({"reply": reply})


@mentor_bp.route("/api/mentor/what-now", methods=["POST"])
@login_required
def api_mentor_what_now():
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured."}), 503
    try:
        data = mentor_what_now(session.get("admin_id"))
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@mentor_bp.route("/api/mentor/review", methods=["POST"])
@login_required
def api_mentor_review():
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured."}), 503
    data = request.get_json(silent=True) or {}
    kind = data.get("kind") or "evening"
    try:
        text = mentor_daily_review(session.get("admin_id"), kind=kind)
        return jsonify({"review": text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@mentor_bp.route("/api/mentor/problems", methods=["POST"])
@login_required
def api_mentor_create_problem():
    data = request.get_json(silent=True) or {}
    try:
        p = create_problem(session.get("admin_id"), data)
        return jsonify(p.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@mentor_bp.route("/api/mentor/problems/<int:problem_id>", methods=["PUT"])
@login_required
def api_mentor_update_problem(problem_id):
    data = request.get_json(silent=True) or {}
    try:
        p = update_problem(problem_id, session.get("admin_id"), data)
        return jsonify(p.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@mentor_bp.route("/api/mentor/check-ins/<int:checkin_id>/respond", methods=["POST"])
@login_required
def api_mentor_checkin_respond(checkin_id):
    data = request.get_json(silent=True) or {}
    try:
        row = respond_checkin(
            checkin_id,
            session.get("admin_id"),
            data.get("response_type") or "",
            data.get("response") or "",
        )
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@mentor_bp.route("/api/mentor/transcribe", methods=["POST"])
@login_required
def api_mentor_transcribe():
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured."}), 503
    upload = request.files.get("audio")
    if not upload:
        return jsonify({"error": "Audio file is required."}), 400
    try:
        text = transcribe_audio(upload)
        return jsonify({"text": text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
