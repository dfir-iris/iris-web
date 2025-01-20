from flask import Blueprint

from app.blueprints.rest.v2.auth import auth_blueprint
from app.blueprints.rest.v2.tasks import tasks_blueprint
from app.blueprints.rest.v2.iocs import iocs_blueprint
from app.blueprints.rest.v2.assets import assets_blueprint
from app.blueprints.rest.v2.alerts import alerts_blueprint
from app.blueprints.rest.v2.dashboard import dashboard_blueprint
from app.blueprints.rest.v2.cases import cases_blueprint


# Create root /api/v2 blueprint
rest_v2_blueprint = Blueprint("rest_v2", __name__, url_prefix="/api/v2")


# Register child blueprints
rest_v2_blueprint.register_blueprint(cases_blueprint)
rest_v2_blueprint.register_blueprint(auth_blueprint)
rest_v2_blueprint.register_blueprint(tasks_blueprint)
rest_v2_blueprint.register_blueprint(iocs_blueprint)
rest_v2_blueprint.register_blueprint(assets_blueprint)
rest_v2_blueprint.register_blueprint(alerts_blueprint)
rest_v2_blueprint.register_blueprint(dashboard_blueprint)
