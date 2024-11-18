#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

# Python modules

# Flask modules

# App modules

from app import app
from app import lm
from app.blueprints.activities.activities_routes import activities_blueprint
from app.blueprints.alerts.alerts_routes import alerts_blueprint
from app.blueprints.api.api_routes import api_blueprint
from app.blueprints.case.case_routes import case_blueprint
from app.blueprints.context.context import ctx_blueprint
# Blueprints
from app.blueprints.graphql.graphql_route import graphql_blueprint
from app.blueprints.dashboard.dashboard_routes import dashboard_blueprint
from app.blueprints.datastore.datastore_routes import datastore_blueprint
from app.blueprints.demo_landing.demo_landing import demo_blueprint
from app.blueprints.dim_tasks.dim_tasks import dim_tasks_blueprint
from app.blueprints.filters.filters_routes import saved_filters_blueprint
from app.blueprints.login.login_routes import login_blueprint
from app.blueprints.manage.manage_access_control import manage_ac_blueprint
from app.blueprints.manage.manage_alerts_status_routes import manage_alerts_status_blueprint
from app.blueprints.manage.manage_analysis_status_routes import manage_anastatus_blueprint
from app.blueprints.manage.manage_assets import manage_assets_blueprint
from app.blueprints.manage.manage_assets_type_routes import manage_assets_type_blueprint
from app.blueprints.manage.manage_attributes_routes import manage_attributes_blueprint
from app.blueprints.manage.manage_case_classifications import manage_case_classification_blueprint
from app.blueprints.manage.manage_case_state import manage_case_state_blueprint
from app.blueprints.manage.manage_evidence_types_route import manage_evidence_types_blueprint
from app.blueprints.manage.manage_cases_routes import manage_cases_blueprint
from app.blueprints.manage.manage_customers_routes import manage_customers_blueprint
from app.blueprints.manage.manage_event_categories_routes import manage_event_cat_blueprint
from app.blueprints.manage.manage_groups import manage_groups_blueprint
from app.blueprints.manage.manage_ioc_types_routes import manage_ioc_type_blueprint
from app.blueprints.manage.manage_modules_routes import manage_modules_blueprint
from app.blueprints.manage.manage_objects_routes import manage_objects_blueprint
from app.blueprints.manage.manage_severities_routes import manage_severities_blueprint
from app.blueprints.manage.manage_srv_settings_routes import manage_srv_settings_blueprint
from app.blueprints.manage.manage_tags import manage_tags_blueprint
from app.blueprints.manage.manage_task_status_routes import manage_task_status_blueprint
from app.blueprints.manage.manage_templates_routes import manage_templates_blueprint
from app.blueprints.manage.manage_tlps_routes import manage_tlp_type_blueprint
from app.blueprints.manage.manage_case_templates_routes import manage_case_templates_blueprint
from app.blueprints.manage.manage_users import manage_users_blueprint
from app.blueprints.overview.overview_routes import overview_blueprint
from app.blueprints.profile.profile_routes import profile_blueprint
from app.blueprints.reports.reports_route import reports_blueprint
from app.blueprints.search.search_routes import search_blueprint
from app.models.authorization import User
from app.post_init import run_post_init


app.register_blueprint(graphql_blueprint)
app.register_blueprint(dashboard_blueprint)
app.register_blueprint(overview_blueprint)
app.register_blueprint(login_blueprint)
app.register_blueprint(profile_blueprint)
app.register_blueprint(search_blueprint)
app.register_blueprint(manage_cases_blueprint)
app.register_blueprint(manage_assets_type_blueprint)
app.register_blueprint(manage_srv_settings_blueprint)
app.register_blueprint(manage_users_blueprint)
app.register_blueprint(manage_templates_blueprint)
app.register_blueprint(manage_modules_blueprint)
app.register_blueprint(manage_customers_blueprint)
app.register_blueprint(manage_anastatus_blueprint)
app.register_blueprint(manage_ioc_type_blueprint)
app.register_blueprint(manage_event_cat_blueprint)
app.register_blueprint(manage_objects_blueprint)
app.register_blueprint(manage_tlp_type_blueprint)
app.register_blueprint(manage_case_templates_blueprint)
app.register_blueprint(manage_task_status_blueprint)
app.register_blueprint(manage_attributes_blueprint)
app.register_blueprint(manage_ac_blueprint)
app.register_blueprint(manage_groups_blueprint)
app.register_blueprint(manage_case_classification_blueprint)
app.register_blueprint(manage_alerts_status_blueprint)
app.register_blueprint(manage_severities_blueprint)
app.register_blueprint(manage_case_state_blueprint)
app.register_blueprint(manage_evidence_types_blueprint)
app.register_blueprint(manage_assets_blueprint)
app.register_blueprint(manage_tags_blueprint)
app.register_blueprint(saved_filters_blueprint)

app.register_blueprint(ctx_blueprint)
app.register_blueprint(case_blueprint)
app.register_blueprint(reports_blueprint)
app.register_blueprint(activities_blueprint)
app.register_blueprint(dim_tasks_blueprint)
app.register_blueprint(datastore_blueprint)
app.register_blueprint(alerts_blueprint)

app.register_blueprint(api_blueprint)
app.register_blueprint(demo_blueprint)

try:

    run_post_init(development=app.config["DEVELOPMENT"])

except Exception as e:
    app.logger.exception(f"Post init failed. IRIS not started")
    raise e


# provide login manager with load_user callback
@lm.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _get_user_by_api_key(api_key):
    if not api_key:
        return None

    api_key = api_key.replace('Bearer ', '', 1)
    return User.query.filter(
        User.api_key == api_key,
        User.active == True
    ).first()


@lm.request_loader
def load_user_from_request(request):
    api_key_sources = [
        request.headers.get('X-IRIS-AUTH'),
        request.headers.get('Authorization')
    ]

    for api_key in api_key_sources:
        if api_key:
            user = _get_user_by_api_key(api_key)
            if user:
                return user

    return None
