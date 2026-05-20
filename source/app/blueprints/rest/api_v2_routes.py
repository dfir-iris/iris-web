#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from flask import Blueprint

from app.blueprints.rest.v2.alerts import alerts_blueprint
from app.blueprints.rest.v2.assets import assets_blueprint
from app.blueprints.rest.v2.events import events_blueprint
from app.blueprints.rest.v2.evidences import evidences_blueprint
from app.blueprints.rest.v2.notes import notes_blueprint
from app.blueprints.rest.v2.auth import auth_blueprint
from app.blueprints.rest.v2.cases import cases_blueprint
from app.blueprints.rest.v2.dashboard import dashboard_blueprint
from app.blueprints.rest.v2.global_tasks import global_tasks_blueprint
from app.blueprints.rest.v2.iocs import iocs_blueprint
from app.blueprints.rest.v2.manage import manage_v2_blueprint
from app.blueprints.rest.v2.tags import tags_blueprint
from app.blueprints.rest.v2.tasks import tasks_blueprint
from app.blueprints.rest.v2.profile import profile_blueprint
from app.blueprints.rest.v2.alerts_filters import alerts_filters_blueprint


# Create root /api/v2 blueprint
rest_v2_blueprint = Blueprint('rest_v2', __name__, url_prefix='/api/v2')

# Register child blueprints
rest_v2_blueprint.register_blueprint(cases_blueprint)
rest_v2_blueprint.register_blueprint(auth_blueprint)
rest_v2_blueprint.register_blueprint(tasks_blueprint)
rest_v2_blueprint.register_blueprint(global_tasks_blueprint)
rest_v2_blueprint.register_blueprint(iocs_blueprint)
rest_v2_blueprint.register_blueprint(assets_blueprint)
rest_v2_blueprint.register_blueprint(events_blueprint)
rest_v2_blueprint.register_blueprint(evidences_blueprint)
rest_v2_blueprint.register_blueprint(notes_blueprint)
rest_v2_blueprint.register_blueprint(alerts_blueprint)
rest_v2_blueprint.register_blueprint(dashboard_blueprint)
rest_v2_blueprint.register_blueprint(manage_v2_blueprint)
rest_v2_blueprint.register_blueprint(tags_blueprint)
rest_v2_blueprint.register_blueprint(profile_blueprint)
rest_v2_blueprint.register_blueprint(alerts_filters_blueprint)
