import os
from flask import Flask, jsonify
from app.config import Config
from app.models.database import Database, close_db
from app.routes.api import api_bp
from app.routes.web import web_bp
import app.tools # Ensure all tools are registered in tool_registry

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # Initialize database
    with app.app_context():
        Database.init_db(app.config.get("DB_PATH"))

    # Register blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    # Teardown database connections
    app.teardown_appcontext(close_db)

    # Error handling
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found", "status_code": 404}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error", "status_code": 500}), 500

    return app
