from flask import Blueprint

from app.blueprints.rest.v2.auth import auth_bp


# Create root /api/v2 blueprint
rest_v2_bp = Blueprint("rest_v2", __name__, url_prefix="/api/v2")


# Register child blueprints
rest_v2_bp.register_blueprint(auth_bp)
