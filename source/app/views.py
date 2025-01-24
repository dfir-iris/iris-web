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


from app.blueprints.pages.activities.activities_routes import activities_blueprint
from app.blueprints.pages.alerts.alerts_routes import alerts_blueprint
from app.blueprints.pages.case.case_routes import case_blueprint
from app.blueprints.pages.case.case_assets_routes import case_assets_blueprint
from app.blueprints.pages.case.case_graphs_routes import case_graph_blueprint
from app.blueprints.pages.case.case_notes_routes import case_notes_blueprint
from app.blueprints.pages.case.case_rfiles_routes import case_rfiles_blueprint
from app.blueprints.pages.case.case_ioc_routes import case_ioc_blueprint
from app.blueprints.pages.case.case_tasks_routes import case_tasks_blueprint
from app.blueprints.pages.case.case_timeline_routes import case_timeline_blueprint
from app.blueprints.pages.dashboard.dashboard_routes import dashboard_blueprint
from app.blueprints.pages.datastore.datastore_routes import datastore_blueprint
from app.blueprints.pages.demo_landing.demo_landing import demo_blueprint
from app.blueprints.pages.dim_tasks.dim_tasks import dim_tasks_blueprint
from app.blueprints.pages.login.login_routes import login_blueprint
from app.blueprints.pages.manage.manage_access_control import manage_ac_blueprint
from app.blueprints.pages.manage.manage_assets_type_routes import manage_assets_type_blueprint
from app.blueprints.pages.manage.manage_attributes_routes import manage_attributes_blueprint
from app.blueprints.pages.manage.manage_case_classification_routes import manage_case_classification_blueprint
from app.blueprints.pages.manage.manage_case_state import manage_case_state_blueprint
from app.blueprints.pages.manage.manage_evidence_types_route import manage_evidence_types_blueprint
from app.blueprints.pages.manage.manage_cases_routes import manage_cases_blueprint
from app.blueprints.pages.manage.manage_customers_routes import manage_customers_blueprint
from app.blueprints.pages.manage.manage_groups_routes import manage_groups_blueprint
from app.blueprints.pages.manage.manage_ioc_types_routes import manage_ioc_type_blueprint
from app.blueprints.pages.manage.manage_modules_routes import manage_modules_blueprint
from app.blueprints.pages.manage.manage_objects_routes import manage_objects_blueprint
from app.blueprints.pages.manage.manage_srv_settings_routes import manage_srv_settings_blueprint
from app.blueprints.pages.manage.manage_templates_routes import manage_templates_blueprint
from app.blueprints.pages.manage.manage_case_templates_routes import manage_case_templates_blueprint
from app.blueprints.pages.manage.manage_users import manage_users_blueprint
from app.blueprints.pages.overview.overview_routes import overview_blueprint
from app.blueprints.pages.profile.profile_routes import profile_blueprint
from app.blueprints.pages.search.search_routes import search_blueprint
from app.blueprints.rest.activities_routes import activities_rest_blueprint
from app.blueprints.rest.alerts_routes import alerts_rest_blueprint
from app.blueprints.rest.api_routes import rest_api_blueprint
from app.blueprints.rest.case.case_assets_routes import case_assets_rest_blueprint
from app.blueprints.rest.case.case_routes import case_rest_blueprint
from app.blueprints.rest.case.case_graphs_routes import case_graph_rest_blueprint
from app.blueprints.rest.case.case_ioc_routes import case_ioc_rest_blueprint
from app.blueprints.rest.case.case_notes_routes import case_notes_rest_blueprint
from app.blueprints.rest.case.case_evidences_routes import case_evidences_rest_blueprint
from app.blueprints.rest.case.case_tasks_routes import case_tasks_rest_blueprint
from app.blueprints.rest.case.case_timeline_routes import case_timeline_rest_blueprint
from app.blueprints.rest.context_routes import context_rest_blueprint
from app.blueprints.rest.dashboard_routes import dashboard_rest_blueprint
from app.blueprints.rest.datastore_routes import datastore_rest_blueprint
from app.blueprints.rest.dim_tasks_routes import dim_tasks_rest_blueprint
from app.blueprints.rest.filters_routes import saved_filters_rest_blueprint
from app.blueprints.rest.manage.manage_access_control_routes import manage_ac_rest_blueprint
from app.blueprints.rest.manage.manage_alerts_status_routes import manage_alerts_status_rest_blueprint
from app.blueprints.rest.manage.manage_analysis_status_routes import manage_analysis_status_rest_blueprint
from app.blueprints.rest.manage.manage_assets_routes import manage_assets_rest_blueprint
from app.blueprints.rest.manage.manage_assets_type_routes import manage_assets_type_rest_blueprint
from app.blueprints.rest.manage.manage_attributes_routes import manage_attributes_rest_blueprint
from app.blueprints.rest.manage.manage_case_classifications_routes import manage_case_classification_rest_blueprint
from app.blueprints.rest.manage.manage_case_state import manage_case_state_rest_blueprint
from app.blueprints.rest.manage.manage_evidence_types_routes import manage_evidence_types_rest_blueprint
from app.blueprints.rest.manage.manage_cases_routes import manage_cases_rest_blueprint
from app.blueprints.rest.manage.manage_customers_routes import manage_customers_rest_blueprint
from app.blueprints.rest.manage.manage_event_categories_routes import manage_event_categories_rest_blueprint
from app.blueprints.rest.manage.manage_groups import manage_groups_rest_blueprint
from app.blueprints.rest.manage.manage_ioc_types_routes import manage_ioc_type_rest_blueprint
from app.blueprints.rest.manage.manage_modules_routes import manage_modules_rest_blueprint
from app.blueprints.rest.manage.manage_severities_routes import manage_severities_rest_blueprint
from app.blueprints.rest.manage.manage_server_settings_routes import manage_server_settings_rest_blueprint
from app.blueprints.rest.manage.manage_tags import manage_tags_rest_blueprint
from app.blueprints.rest.manage.manage_task_status_routes import manage_task_status_rest_blueprint
from app.blueprints.rest.manage.manage_templates_routes import manage_templates_rest_blueprint
from app.blueprints.rest.manage.manage_tlps_routes import manage_tlp_type_rest_blueprint
from app.blueprints.rest.manage.manage_case_templates_routes import manage_case_templates_rest_blueprint
from app.blueprints.rest.manage.manage_users import manage_users_rest_blueprint
from app.blueprints.rest.overview_routes import overview_rest_blueprint
from app.blueprints.rest.profile_routes import profile_rest_blueprint
from app.blueprints.rest.reports_route import reports_rest_blueprint
from app.blueprints.rest.search_routes import search_rest_blueprint
from app.blueprints.graphql.graphql_route import graphql_blueprint

from app.blueprints.rest.v2 import rest_v2_blueprint
from app.models.authorization import User

def register_blusprints(app):
    app.register_blueprint(graphql_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(dashboard_rest_blueprint)
    app.register_blueprint(overview_blueprint)
    app.register_blueprint(overview_rest_blueprint)
    app.register_blueprint(login_blueprint)
    app.register_blueprint(profile_blueprint)
    app.register_blueprint(profile_rest_blueprint)
    app.register_blueprint(search_blueprint)
    app.register_blueprint(search_rest_blueprint)
    app.register_blueprint(manage_cases_blueprint)
    app.register_blueprint(manage_cases_rest_blueprint)
    app.register_blueprint(manage_assets_type_blueprint)
    app.register_blueprint(manage_assets_type_rest_blueprint)
    app.register_blueprint(manage_srv_settings_blueprint)
    app.register_blueprint(manage_server_settings_rest_blueprint)
    app.register_blueprint(manage_users_blueprint)
    app.register_blueprint(manage_users_rest_blueprint)
    app.register_blueprint(manage_templates_blueprint)
    app.register_blueprint(manage_templates_rest_blueprint)
    app.register_blueprint(manage_modules_blueprint)
    app.register_blueprint(manage_modules_rest_blueprint)
    app.register_blueprint(manage_customers_blueprint)
    app.register_blueprint(manage_customers_rest_blueprint)
    app.register_blueprint(manage_analysis_status_rest_blueprint)
    app.register_blueprint(manage_ioc_type_blueprint)
    app.register_blueprint(manage_ioc_type_rest_blueprint)
    app.register_blueprint(manage_event_categories_rest_blueprint)
    app.register_blueprint(manage_objects_blueprint)
    app.register_blueprint(manage_tlp_type_rest_blueprint)
    app.register_blueprint(manage_case_templates_blueprint)
    app.register_blueprint(manage_case_templates_rest_blueprint)
    app.register_blueprint(manage_task_status_rest_blueprint)
    app.register_blueprint(manage_attributes_blueprint)
    app.register_blueprint(manage_attributes_rest_blueprint)
    app.register_blueprint(manage_ac_blueprint)
    app.register_blueprint(manage_ac_rest_blueprint)
    app.register_blueprint(manage_groups_blueprint)
    app.register_blueprint(manage_groups_rest_blueprint)
    app.register_blueprint(manage_case_classification_blueprint)
    app.register_blueprint(manage_case_classification_rest_blueprint)
    app.register_blueprint(manage_alerts_status_rest_blueprint)
    app.register_blueprint(manage_severities_rest_blueprint)
    app.register_blueprint(manage_case_state_blueprint)
    app.register_blueprint(manage_case_state_rest_blueprint)
    app.register_blueprint(manage_evidence_types_blueprint)
    app.register_blueprint(manage_evidence_types_rest_blueprint)
    app.register_blueprint(manage_assets_rest_blueprint)
    app.register_blueprint(manage_tags_rest_blueprint)
    app.register_blueprint(saved_filters_rest_blueprint)

    app.register_blueprint(context_rest_blueprint)
    app.register_blueprint(case_timeline_blueprint)
    app.register_blueprint(case_timeline_rest_blueprint)
    app.register_blueprint(case_notes_blueprint)
    app.register_blueprint(case_notes_rest_blueprint)
    app.register_blueprint(case_assets_blueprint)
    app.register_blueprint(case_assets_rest_blueprint)
    app.register_blueprint(case_ioc_blueprint)
    app.register_blueprint(case_ioc_rest_blueprint)
    app.register_blueprint(case_rfiles_blueprint)
    app.register_blueprint(case_evidences_rest_blueprint)
    app.register_blueprint(case_graph_blueprint)
    app.register_blueprint(case_graph_rest_blueprint)
    app.register_blueprint(case_tasks_blueprint)
    app.register_blueprint(case_tasks_rest_blueprint)
    app.register_blueprint(case_blueprint)
    app.register_blueprint(case_rest_blueprint)
    app.register_blueprint(reports_rest_blueprint)
    app.register_blueprint(activities_blueprint)
    app.register_blueprint(activities_rest_blueprint)
    app.register_blueprint(dim_tasks_blueprint)
    app.register_blueprint(dim_tasks_rest_blueprint)
    app.register_blueprint(datastore_blueprint)
    app.register_blueprint(datastore_rest_blueprint)
    app.register_blueprint(alerts_blueprint)
    app.register_blueprint(alerts_rest_blueprint)

    app.register_blueprint(rest_api_blueprint)
    app.register_blueprint(demo_blueprint)

    app.register_blueprint(rest_v2_blueprint)



# provide login manager with load_user callback
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
