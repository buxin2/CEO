from flask import Blueprint, current_app, jsonify, request, session

from routes.auth import login_required
from services.ai_assistant import run_agent
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

    trimmed_history = []
    for item in history[-24:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            trimmed_history.append({"role": role, "content": content})

    context = dict(session.get("ai_context") or {})
    user_messages = list(trimmed_history)
    user_messages.append({"role": "user", "content": message})

    try:
        reply = run_agent(user_messages, context)
    except Exception as exc:
        current_app.logger.exception("AI chat failed")
        return jsonify({"error": f"AI request failed: {exc}"}), 500

    session["ai_context"] = context
    session.modified = True

    return jsonify({"reply": reply})


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
