import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request

from config import config_by_name
from models import db, Admin, Company, CompanyGroup


def _origin_allowed(origin, allowed_origins):
    if not origin:
        return False
    normalized = origin.rstrip("/")
    allowed = {o.rstrip("/") for o in allowed_origins}
    return normalized in allowed


def create_app():
    app = Flask(__name__)

    env_name = os.environ.get("FLASK_ENV", "production")
    app.config.from_object(config_by_name.get(env_name, config_by_name["production"]))

    cors_origins = list(app.config["CORS_ORIGINS"])
    app.logger.info("CORS allowed origins: %s", cors_origins)

    @app.before_request
    def cors_preflight():
        if request.method != "OPTIONS":
            return None

        origin = request.headers.get("Origin")
        if not _origin_allowed(origin, cors_origins):
            app.logger.warning("CORS preflight rejected for origin: %s", origin)
            return None

        response = app.make_response("")
        response.status_code = 204
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Employee-Token"
        response.headers["Vary"] = "Origin"
        return response

    @app.after_request
    def cors_headers(response):
        origin = request.headers.get("Origin")
        if _origin_allowed(origin, cors_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.company import company_bp
    from routes.employee import employee_bp
    from routes.public import public_bp
    from routes.group import group_bp
    from routes.ai import ai_bp
    from routes.catalog import catalog_bp
    from routes.planner import planner_bp
    from routes.news import news_bp
    from routes.mentor import mentor_bp
    from routes.community import community_bp
    from routes.payments import payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(payments_bp)

    @app.route("/")
    def index():
        return jsonify({
            "status": "ok",
            "message": "CEO API is running. Admin UI is on GitHub Pages.",
            "health": "/api/health",
            "frontend": app.config["FRONTEND_URL"],
            "cors_origins": cors_origins,
        })

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        from services.schema_migrations import run_schema_migrations

        run_schema_migrations()
        _ensure_admin_account(app)
        from services.owner_profile_service import ensure_owner_display_names

        ensure_owner_display_names(app)
        _ensure_company_groups(app)
        from services.opportunity_scheduler import start_opportunity_scheduler
        from services.mentor_scheduler import start_mentor_scheduler

        start_opportunity_scheduler(app)
        start_mentor_scheduler(app)
        from services.community_scheduler import start_community_scheduler

        start_community_scheduler(app)

    return app


def _ensure_company_groups(app):
    """Create groups for existing companies that don't have one yet."""
    companies = Company.query.all()
    for company in companies:
        if not company.group:
            db.session.add(CompanyGroup(company_id=company.id))
    db.session.commit()


def _ensure_admin_account(app):
    """Create the initial admin account from environment variables if it doesn't exist."""
    admin_email = app.config["ADMIN_EMAIL"].strip().lower()
    admin_password = app.config["ADMIN_PASSWORD"]

    existing = Admin.query.filter_by(email=admin_email).first()
    if existing:
        return

    admin = Admin(email=admin_email)
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()
    app.logger.info(f"Created initial admin account: {admin_email}")


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
