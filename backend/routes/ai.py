from flask import Blueprint, current_app, jsonify, request, session

from routes.auth import login_required
from services.ai_assistant import run_agent

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ai/status", methods=["GET"])
@login_required
def ai_status():
    configured = bool(current_app.config.get("GROQ_API_KEY"))
    return jsonify({
        "configured": configured,
        "model": current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
    })


@ai_bp.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    if not current_app.config.get("GROQ_API_KEY"):
        return jsonify({"error": "AI assistant is not configured. Set GROQ_API_KEY on the server."}), 503

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    history = data.get("history") or []
    if not isinstance(history, list):
        history = []

    # Keep recent conversation for context without blowing token limits
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
