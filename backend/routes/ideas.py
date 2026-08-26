"""My Ideas API."""

from flask import Blueprint, jsonify, request, session

from routes.auth import login_required
from services.ai_transcribe import transcribe_audio
from services.groq_key_service import is_groq_configured
from services.ideas_ai import idea_action, start_or_continue_chat
from services.ideas_service import (
    add_attachment,
    archive_idea,
    create_idea,
    delete_idea,
    get_idea,
    list_ideas,
    list_messages,
    restore_idea,
    update_idea,
)

ideas_bp = Blueprint("ideas", __name__)


@ideas_bp.route("/api/ideas", methods=["GET"])
@login_required
def api_list_ideas():
    admin_id = session.get("admin_id")
    search = request.args.get("search")
    tag = request.args.get("tag")
    archived = request.args.get("archived", "false").lower() == "true"
    status = request.args.get("status")
    rows = list_ideas(admin_id, search=search, tag=tag, archived=archived, status=status)
    return jsonify({"ideas": [i.to_dict() for i in rows]})


@ideas_bp.route("/api/ideas/<int:idea_id>", methods=["GET"])
@login_required
def api_get_idea(idea_id):
    admin_id = session.get("admin_id")
    try:
        idea = get_idea(admin_id, idea_id)
        data = idea.to_dict(include_detail=True)
        data["messages"] = [m.to_dict() for m in list_messages(idea_id)]
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ideas_bp.route("/api/ideas/<int:idea_id>", methods=["PUT"])
@login_required
def api_update_idea(idea_id):
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    try:
        idea = update_idea(admin_id, idea_id, data)
        return jsonify(idea.to_dict(include_detail=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ideas_bp.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
@login_required
def api_delete_idea(idea_id):
    admin_id = session.get("admin_id")
    try:
        delete_idea(admin_id, idea_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ideas_bp.route("/api/ideas/<int:idea_id>/archive", methods=["POST"])
@login_required
def api_archive_idea(idea_id):
    admin_id = session.get("admin_id")
    try:
        idea = archive_idea(admin_id, idea_id)
        return jsonify(idea.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ideas_bp.route("/api/ideas/<int:idea_id>/restore", methods=["POST"])
@login_required
def api_restore_idea(idea_id):
    admin_id = session.get("admin_id")
    try:
        idea = restore_idea(admin_id, idea_id)
        return jsonify(idea.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ideas_bp.route("/api/ideas/<int:idea_id>/messages", methods=["GET"])
@login_required
def api_idea_messages(idea_id):
    admin_id = session.get("admin_id")
    try:
        get_idea(admin_id, idea_id)
        return jsonify({"messages": [m.to_dict() for m in list_messages(idea_id)]})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ideas_bp.route("/api/ideas/chat", methods=["POST"])
@login_required
def api_ideas_chat():
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured. Add a Groq API key in Admin → AI."}), 503

    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    idea_id = data.get("idea_id")
    create_new = bool(data.get("create_new"))

    try:
        result = start_or_continue_chat(admin_id, message, idea_id=idea_id, create_new=create_new)
        idea = result["idea"]
        msgs = list_messages(idea["id"])
        idea["messages"] = [m.to_dict() for m in msgs]
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ideas_bp.route("/api/ideas/<int:idea_id>/action/<action>", methods=["POST"])
@login_required
def api_idea_action(idea_id, action):
    if not is_groq_configured():
        return jsonify({"error": "AI is not configured."}), 503

    admin_id = session.get("admin_id")
    try:
        text = idea_action(admin_id, idea_id, action)
        idea = get_idea(admin_id, idea_id)
        return jsonify({
            "text": text,
            "idea": idea.to_dict(include_detail=True),
            "messages": [m.to_dict() for m in list_messages(idea_id)],
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ideas_bp.route("/api/ideas/<int:idea_id>/attachments", methods=["POST"])
@login_required
def api_idea_attachment(idea_id):
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    try:
        get_idea(admin_id, idea_id)
        row = add_attachment(
            idea_id,
            data.get("url"),
            title=data.get("title") or "",
            kind=data.get("kind") or "url",
        )
        return jsonify(row.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ideas_bp.route("/api/ideas/transcribe", methods=["POST"])
@login_required
def api_ideas_transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file."}), 400
    try:
        text = transcribe_audio(request.files["audio"])
        return jsonify({"text": text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
