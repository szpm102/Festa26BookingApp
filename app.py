import os

from dotenv import load_dotenv

# Load environment variables from a local env file before Config reads them.
# Supports both the conventional ".env" and this project's "config.env".
_basedir = os.path.abspath(os.path.dirname(__file__))
for _env_filename in (".env", "config.env"):
    _env_path = os.path.join(_basedir, _env_filename)
    if os.path.exists(_env_path):
        load_dotenv(_env_path)

from flask import Flask

from config import Config
from extensions import db, login_manager, csrf, limiter
from models import Admin


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    from routes_public import public_bp
    from routes_api import api_bp
    from routes_admin import admin_bp
    from webhooks import webhooks_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(webhooks_bp)

    with app.app_context():
        db.create_all()

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    # Default OFF: Flask's debug mode exposes an interactive in-browser
    # debugger that can execute arbitrary code - a serious risk if this ever
    # runs reachable from the internet. Opt in explicitly for local dev only.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
