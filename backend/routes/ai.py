from flask import Blueprint, current_app, jsonify, request, session

from routes.auth import login_required
from services.ai_assistant import run_agent, sanitize_chat_history
from services.owner_profile_service import get_owner_profile, update_owner_profile
from services.ai_transcribe import transcribe_audio
from services.groq_key_service import (
    is_groq_configured,
    get_active_groq_config,
    list_keys,
    create_key,
    update_key,
    delete_key,
    activate_key,
    test_saved_key,
    default_model,
)

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ai/status", methods=["GET"])
@login_required
def ai_status():
    config = get_active_groq_config()
    active = None
    if config and config.get("key_id"):
        from models import GroqApiKey

        record = GroqApiKey.query.get(config["key_id"])
        if record:
            active = record.to_dict()

    return jsonify({
        "configured": config is not None,
        "model": config["model"] if config else default_model(),
        "source": config["source"] if config else None,
        "active_key": active,
        "active_key_name": config.get("key_name") if config else None,
    })


@ai_bp.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    if not is_groq_configured():
        return jsonify({
            "error": "AI is not configured. Add a Groq API key below or set GROQ_API_KEY on the server.",
        }), 503

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    history = data.get("history") or []
    if not isinstance(history, list):
        history = []

    trimmed_history = sanitize_chat_history(history)

    context = dict(session.get("ai_context") or {})
    context["admin_id"] = session.get("admin_id")
    user_messages = list(trimmed_history)
    user_messages.append({"role": "user", "content": message})

    try:
        reply = run_agent(
            user_messages,
            context,
            mode=data.get("mode") or "chat",
            admin_id=session.get("admin_id"),
        )
    except Exception as exc:
        current_app.logger.exception("AI chat failed")
        err_text = str(exc)
        if err_text.startswith("Groq API rate limit"):
            return jsonify({"error": err_text}), 429
        return jsonify({"error": f"AI request failed: {err_text}"}), 500

    session["ai_context"] = context
    session.modified = True

    return jsonify({"reply": reply})


@ai_bp.route("/api/ai/profile", methods=["GET"])
@login_required
def ai_get_profile():
    admin_id = session.get("admin_id")
    profile = get_owner_profile(admin_id)
    if not profile:
        return jsonify({"error": "No admin profile found."}), 404
    data = profile.to_dict()
    admin = profile.admin
    if admin:
        data["email"] = admin.email
    return jsonify(data)


@ai_bp.route("/api/ai/profile", methods=["PUT"])
@login_required
def ai_update_profile():
    admin_id = session.get("admin_id")
    data = request.get_json(silent=True) or {}
    try:
        profile = update_owner_profile(
            admin_id,
            display_name=data.get("display_name"),
            profile_text=data.get("profile_text"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    result = profile.to_dict()
    if profile.admin:
        result["email"] = profile.admin.email
    return jsonify(result)


@ai_bp.route("/api/ai/transcribe", methods=["POST"])
@login_required
def ai_transcribe():
    if not is_groq_configured():
        return jsonify({
            "error": "AI is not configured. Add a Groq API key to use voice transcription.",
        }), 503

    upload = request.files.get("audio")
    if not upload:
        return jsonify({"error": "Audio file is required."}), 400

    try:
        text = transcribe_audio(upload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("AI transcribe failed")
        return jsonify({"error": f"Transcription failed: {exc}"}), 500

    return jsonify({"text": text})


@ai_bp.route("/api/ai/groq-keys", methods=["GET"])
@login_required
def api_list_groq_keys():
    keys = list_keys()
    active = next((k for k in keys if k.is_active), None)
    return jsonify({
        "keys": [k.to_dict() for k in keys],
        "active_key_id": active.id if active else None,
        "env_fallback_available": bool((current_app.config.get("GROQ_API_KEY") or "").strip()),
    })


@ai_bp.route("/api/ai/groq-keys", methods=["POST"])
@login_required
def api_create_groq_key():
    data = request.get_json(silent=True) or {}
    try:
        record = create_key(
            name=data.get("name"),
            api_key=data.get("api_key"),
            description=data.get("description"),
            model=data.get("model"),
        )
        return jsonify(record.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ai_bp.route("/api/ai/groq-keys/<int:key_id>", methods=["PUT"])
@login_required
def api_update_groq_key(key_id):
    data = request.get_json(silent=True) or {}
    try:
        record = update_key(
            key_id,
            name=data.get("name"),
            api_key=data.get("api_key"),
            description=data.get("description"),
            model=data.get("model"),
        )
        return jsonify(record.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ai_bp.route("/api/ai/groq-keys/<int:key_id>", methods=["DELETE"])
@login_required
def api_delete_groq_key(key_id):
    from models import GroqApiKey

    record = GroqApiKey.query.get(key_id)
    if not record:
        return jsonify({"error": "API key not found."}), 404

    if record.is_active:
        others = GroqApiKey.query.filter(GroqApiKey.id != key_id).count()
        env = bool((current_app.config.get("GROQ_API_KEY") or "").strip())
        if others == 0 and not env:
            return jsonify({
                "error": "Cannot delete the only active API. Add another key first or keep the environment variable.",
            }), 400

    try:
        result = delete_key(key_id)
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ai_bp.route("/api/ai/groq-keys/<int:key_id>/activate", methods=["POST"])
@login_required
def api_activate_groq_key(key_id):
    try:
        record = activate_key(key_id)
        return jsonify(record.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ai_bp.route("/api/ai/groq-keys/<int:key_id>/test", methods=["POST"])
@login_required
def api_test_groq_key(key_id):
    try:
        result = test_saved_key(key_id)
        record = list_keys()
        key = next((k for k in record if k.id == key_id), None)
        return jsonify({
            **result,
            "key": key.to_dict() if key else None,
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@ai_bp.route("/api/ai/cloudinary", methods=["GET"])
@login_required
def api_cloudinary_get():
    from services.cloudinary_settings_service import settings_to_dict

    try:
        return jsonify(settings_to_dict())
    except Exception as exc:
        current_app.logger.exception("Cloudinary settings load failed")
        return jsonify({"error": f"Could not load Cloudinary settings: {exc}"}), 500


@ai_bp.route("/api/ai/cloudinary", methods=["PUT"])
@login_required
def api_cloudinary_put():
    from services.cloudinary_settings_service import update_settings

    data = request.get_json(silent=True) or {}
    try:
        result = update_settings(
            cloud_name=data.get("cloud_name"),
            api_key=data.get("api_key"),
            api_secret=data.get("api_secret"),
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Cloudinary settings save failed")
        return jsonify({"error": f"Could not save Cloudinary settings: {exc}"}), 500
