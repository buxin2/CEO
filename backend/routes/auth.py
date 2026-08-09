from functools import wraps

from flask import Blueprint, request, jsonify, session

from models import db, Admin
from utils import frontend_url

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    """Decorator that protects admin API routes."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    admin = Admin.query.filter_by(email=email).first()

    if not admin or not admin.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["admin_id"] = admin.id
    session.permanent = True

    return jsonify({"success": True, "redirect": frontend_url("dashboard.html")})


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "redirect": frontend_url("login.html")})


@auth_bp.route("/api/me", methods=["GET"])
def api_me():
    if not session.get("admin_id"):
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True})
