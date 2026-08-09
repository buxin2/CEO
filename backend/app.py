import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS

from config import config_by_name
from models import db, Admin


def create_app():
    app = Flask(__name__)

    env_name = os.environ.get("FLASK_ENV", "production")
    app.config.from_object(config_by_name.get(env_name, config_by_name["production"]))

    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=True,
    )

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.company import company_bp
    from routes.employee import employee_bp
    from routes.public import public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(public_bp)

    @app.route("/")
    def index():
        return jsonify({
            "status": "ok",
            "message": "CEO API is running. Admin UI is on GitHub Pages.",
            "health": "/api/health",
            "frontend": app.config["FRONTEND_URL"],
        })

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        _ensure_admin_account(app)

    return app


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
