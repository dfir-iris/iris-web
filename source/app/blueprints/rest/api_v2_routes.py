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

from app.blueprints.rest.v2.activities import activities_blueprint
from app.blueprints.rest.v2.alerts import alerts_blueprint
from app.blueprints.rest.v2.assets import assets_blueprint
from app.blueprints.rest.v2.events import events_blueprint
from app.blueprints.rest.v2.evidences import evidences_blueprint
from app.blueprints.rest.v2.notes import notes_blueprint
from app.blueprints.rest.v2.auth import auth_blueprint
from app.blueprints.rest.v2.cases import cases_blueprint
from app.blueprints.rest.v2.custom_dashboards import custom_dashboards_blueprint
from app.blueprints.rest.v2.dashboard import dashboard_blueprint
from app.blueprints.rest.v2.dim_tasks import dim_tasks_blueprint
from app.blueprints.rest.v2.global_tasks import global_tasks_blueprint
from app.blueprints.rest.v2.iocs import iocs_blueprint
from app.blueprints.rest.v2.manage import manage_v2_blueprint
from app.blueprints.rest.v2.tags import tags_blueprint
from app.blueprints.rest.v2.tasks import tasks_blueprint
from app.blueprints.rest.v2.profile import profile_blueprint
from app.blueprints.rest.v2.search import search_blueprint
from app.blueprints.rest.v2.avatars import admin_avatar_blueprint
from app.blueprints.rest.v2.avatars import me_avatar_blueprint
from app.blueprints.rest.v2.avatars import users_public_blueprint
from app.blueprints.rest.v2.cases_filters import cases_filters_blueprint
from app.blueprints.rest.v2.war_rooms.root import war_rooms_blueprint
from app.blueprints.rest.v2.notifications import notifications_blueprint
from app.blueprints.rest.v2.notifications import admin_notifications_blueprint
from app.blueprints.rest.v2.mail import mail_blueprint
from app.blueprints.rest.v2.alert_clusters import alert_clusters_blueprint
from app.blueprints.rest.v2.cluster_rules import cluster_rules_blueprint
from app.blueprints.rest.v2.investigation_flows import investigation_flows_blueprint


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
rest_v2_blueprint.register_blueprint(custom_dashboards_blueprint)
rest_v2_blueprint.register_blueprint(dashboard_blueprint)
rest_v2_blueprint.register_blueprint(manage_v2_blueprint)
rest_v2_blueprint.register_blueprint(tags_blueprint)
rest_v2_blueprint.register_blueprint(profile_blueprint)
rest_v2_blueprint.register_blueprint(search_blueprint)
rest_v2_blueprint.register_blueprint(cases_filters_blueprint)
rest_v2_blueprint.register_blueprint(users_public_blueprint)
rest_v2_blueprint.register_blueprint(me_avatar_blueprint)
rest_v2_blueprint.register_blueprint(admin_avatar_blueprint)
rest_v2_blueprint.register_blueprint(activities_blueprint)
rest_v2_blueprint.register_blueprint(dim_tasks_blueprint)
rest_v2_blueprint.register_blueprint(war_rooms_blueprint)
rest_v2_blueprint.register_blueprint(notifications_blueprint)
rest_v2_blueprint.register_blueprint(admin_notifications_blueprint)
rest_v2_blueprint.register_blueprint(mail_blueprint)
rest_v2_blueprint.register_blueprint(alert_clusters_blueprint)
rest_v2_blueprint.register_blueprint(cluster_rules_blueprint)
rest_v2_blueprint.register_blueprint(investigation_flows_blueprint)
