#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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
from flask import session
from flask import request
from flask import Response
from marshmallow.exceptions import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.blueprints.rest.v2.alerts_routes.comments import alerts_comments_blueprint
from app.blueprints.rest.v2.alerts_routes.investigation_progress import alerts_investigation_progress_blueprint
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.manage.manage_access_control_db import check_ua_case_client
from app.business.alerts import alerts_search
from app.business.alerts import alerts_create
from app.business.alerts import alerts_get
from app.business.alerts import alerts_update
from app.business.alerts import alerts_delete
from app.business.alerts import alerts_get_related
from app.business.alerts import alerts_escalate
from app.business.alerts import alerts_merge
from app.business.alerts import alerts_unmerge
from app.business.alerts import alerts_batch_escalate
from app.business.alerts import alerts_batch_merge
from app.business.alerts_filters import alert_filter_add
from app.business.alerts_filters import alert_filter_get
from app.business.alerts_filters import alert_filter_update
from app.business.alerts_filters import alert_filter_delete
from app.business.alerts_filters import alert_filter_list
from app.datamgmt.alerts.alerts_db import get_alert_by_id
from app.models.authorization import Permissions
from app.schema.marshables import AlertSchema
from app.schema.marshables import CaseSchema
from app.schema.marshables import IocSchema
from app.schema.marshables import CaseAssetsSchema
from app.schema.marshables import SavedFilterSchema
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


# Fields that must be immutable on alert update. See GHSA-8hwq-v6vm-9grr
# / SBA-ADV-20260128-05 / CWE-863 — re-attributing alert_customer_id lets
# a user with write access to one tenant move an alert under a tenant they
# cannot see; alert_id is the primary key; alert_creation_time is audit
# integrity (set once at creation).
_ALERT_READONLY_UPDATE_FIELDS = frozenset({
    'alert_id',
    'alert_customer_id',
    'alert_creation_time',
})


def _strip_readonly_alert_fields(payload):
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k not in _ALERT_READONLY_UPDATE_FIELDS}


class AlertsOperations:

    def __init__(self):
        self._schema = AlertSchema()

    def search(self):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        alert_ids_str = request.args.get('alert_ids')
        alert_ids = None
        if alert_ids_str:
            try:

                alert_ids = parse_comma_separated_identifiers(alert_ids_str)

            except ValueError:
                return response_api_error('Invalid alert id')

        alert_assets_str = request.args.get('alert_assets')
        alert_assets = None
        if alert_assets_str:
            try:
                alert_assets = [str(alert_asset)
                                for alert_asset in alert_assets_str.split(',')]

            except ValueError:
                return response_api_error('Invalid alert asset')

        alert_iocs_str = request.args.get('alert_iocs')
        alert_iocs = None
        if alert_iocs_str:
            try:
                alert_iocs = [str(alert_ioc)
                              for alert_ioc in alert_iocs_str.split(',')]

            except ValueError:
                return response_api_error('Invalid alert ioc')

        fields_str = request.args.get('fields')
        if fields_str:
            # Split into a list
            fields = [field.strip() for field in fields_str.split(',') if field.strip()]
        else:
            fields = None

        user_identifier_filter = iris_current_user.id
        if ac_current_user_has_permission(Permissions.server_administrator):
            user_identifier_filter = None

        filtered_alerts = alerts_search(
            request.args.get('creation_start_date'),
            request.args.get('creation_end_date'),
            request.args.get('source_start_date'),
            request.args.get('source_end_date'),
            request.args.get('alert_title'),
            request.args.get('alert_description'),
            request.args.get('alert_status_id', type=int),
            request.args.get('alert_severity_id', type=int),
            request.args.get('alert_owner_id', type=int),
            request.args.get('alert_source'),
            request.args.get('alert_tags'),
            request.args.get('case_id', type=int),
            request.args.get('alert_customer_id'),
            request.args.get('alert_classification_id', type=int),
            alert_ids,
            alert_assets,
            alert_iocs,
            request.args.get('alert_resolution_id', type=int),
            request.args.get('source_reference'),
            request.args.get('custom_conditions'),
            user_identifier_filter,
            page,
            per_page,
            request.args.get('sort'),
            request.args.get('cluster_id', type=int),
        )

        if filtered_alerts is None:
            return response_api_error('Filtering error')

        # If fields are provided, use them in the schema
        if fields:
            try:
                alert_schema = AlertSchema(only=fields)
            except Exception:
                alert_schema = self._schema
        else:
            alert_schema = self._schema

        return response_api_paginated(alert_schema, filtered_alerts)

    def create(self):
        request_data = request.get_json()
        iocs_list = request_data.pop('alert_iocs', [])
        ioc_schema = IocSchema()
        iocs = ioc_schema.load(iocs_list, many=True, partial=True)

        assets_list = request_data.pop('alert_assets', [])
        asset_schema = CaseAssetsSchema()
        assets = asset_schema.load(assets_list, many=True, partial=True)

        try:
            alert = self._schema.load(request_data)
            result = alerts_create(alert, iocs, assets)

            if not ac_current_user_has_customer_access(result.alert_customer_id):
                return response_api_error('User not entitled to create alerts for the client')
            return response_api_created(self._schema.dump(result))

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def read(self, identifier):

        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            return response_api_success(self._schema.dump(alert))

        except ObjectNotFoundError:
            return response_api_not_found()

    def get_related_alerts(self, identifier):

        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )

            open_alerts = request.args.get('open-alerts', 'false').lower() == 'true'
            closed_alerts = request.args.get('closed-alerts', 'false').lower() == 'true'

            open_cases_arg = request.args.get('open-cases')
            closed_cases_arg = request.args.get('closed-cases')

            if open_cases_arg is None and closed_cases_arg is None:
                open_cases = True
                closed_cases = True
            else:
                open_cases = (open_cases_arg or 'false').lower() == 'true'
                closed_cases = (closed_cases_arg or 'false').lower() == 'true'

            days_back = request.args.get('days-back', 180, type=int)
            number_of_results = request.args.get('number-of-nodes', 100, type=int)

            if number_of_results < 0:
                number_of_results = 100
            if days_back < 0:
                days_back = 180

            similar_alerts = alerts_get_related(
                iris_current_user,
                alert,
                open_alerts,
                closed_alerts,
                open_cases,
                closed_cases,
                days_back,
                number_of_results
            )

            return response_api_success(similar_alerts)

        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):
        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            # Drop fields the caller must not be allowed to change on update
            # (GHSA-8hwq-v6vm-9grr / SBA-ADV-20260128-05 / CWE-863). The
            # customer_id is the worst: re-attributing an alert to a
            # customer the caller cannot see hides it from the rightful
            # owner and plants it under another tenant's view.
            request_data = _strip_readonly_alert_fields(request.get_json())
            iocs_list = request_data.pop('alert_iocs', None)
            updated_alert = self._schema.load(request_data, instance=alert, partial=True)
            activity_data = []

            for key, value in request_data.items():
                old_value = getattr(alert, key, None)

                if type(old_value) is int:
                    old_value = str(old_value)

                if type(value) is int:
                    value = str(value)

                    if key not in ["alert_content", "alert_note"]:
                        activity_data.append(f"\"{key}\" from \"{old_value}\" to \"{value}\"")
                    else:
                        activity_data.append(f"\"{key}\"")
            if request_data.get('alert_owner_id') is None and updated_alert.alert_owner_id is None:
                updated_alert.alert_owner_id = iris_current_user.id

            if request_data.get('alert_owner_id') == "-1" or request_data.get('alert_owner_id') == -1:
                updated_alert.alert_owner_id = None

            if iocs_list is not None:
                ioc_schema = IocSchema()
                updated_alert.iocs = ioc_schema.load(iocs_list, many=True, partial=True)
                activity_data.append('"alert_iocs"')

            result = alerts_update(alert, updated_alert, activity_data)
            return response_api_success(self._schema.dump(result))

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            alerts_delete(alert)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()


alerts_blueprint = Blueprint('alerts_rest_v2', __name__, url_prefix='/alerts')
alerts_blueprint.register_blueprint(alerts_comments_blueprint)
alerts_blueprint.register_blueprint(alerts_investigation_progress_blueprint)

alerts_operations = AlertsOperations()


@alerts_blueprint.get('')
@ac_api_requires(Permissions.alerts_read)
def alerts_list_route() -> Response:
    return alerts_operations.search()


@alerts_blueprint.post('')
@ac_api_requires(Permissions.alerts_write)
def create_alert():
    return alerts_operations.create()


@alerts_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.alerts_read)
def get_alert(identifier):
    return alerts_operations.read(identifier)


@alerts_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def update_alert(identifier):
    return alerts_operations.update(identifier)


@alerts_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.alerts_delete)
def delete_alert(identifier):
    return alerts_operations.delete(identifier)


@alerts_blueprint.get('/<int:identifier>/related-alerts')
@ac_api_requires(Permissions.alerts_read)
def get_related_alerts(identifier):
    return alerts_operations.get_related_alerts(identifier)


@alerts_blueprint.post('/escalate/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def escalate_alert(identifier):
    alert = get_alert_by_id(identifier)
    if not alert:
        return response_api_not_found()

    if not ac_current_user_has_customer_access(alert.alert_customer_id):
        return response_api_error('User not entitled to escalate alerts for the client')

    data = request.get_json() or {}
    try:
        case = alerts_escalate(
            alert,
            iocs_import_list=data.get('iocs_import_list'),
            assets_import_list=data.get('assets_import_list'),
            note=data.get('note'),
            import_as_event=data.get('import_as_event'),
            case_tags=data.get('case_tags'),
            case_title=data.get('case_title'),
            case_template_id=data.get('case_template_id'),
        )
        return response_api_success(CaseSchema().dump(case))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@alerts_blueprint.post('/merge/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def merge_alert(identifier):
    data = request.get_json() or {}
    target_case_id = data.get('target_case_id')
    if target_case_id is None:
        return response_api_error('No target case id provided')

    alert = get_alert_by_id(identifier)
    if not alert:
        return response_api_not_found()

    if not ac_current_user_has_customer_access(alert.alert_customer_id):
        return response_api_error('User not entitled to merge alerts for the client')
    if not check_ua_case_client(iris_current_user.id, target_case_id):
        return response_api_error('User not entitled to merge alerts for the case')

    try:
        case = alerts_merge(
            alert,
            target_case_id=target_case_id,
            iocs_import_list=data.get('iocs_import_list'),
            assets_import_list=data.get('assets_import_list'),
            note=data.get('note'),
            import_as_event=data.get('import_as_event'),
            case_tags=data.get('case_tags'),
        )
        return response_api_success(CaseSchema().dump(case))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@alerts_blueprint.post('/unmerge/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def unmerge_alert(identifier):
    data = request.get_json() or {}
    target_case_id = data.get('target_case_id')
    if target_case_id is None:
        return response_api_error('No target case id provided')

    alert = get_alert_by_id(identifier)
    if not alert:
        return response_api_not_found()

    if not ac_current_user_has_customer_access(alert.alert_customer_id):
        return response_api_error('User not entitled to unmerge alerts for the client')
    if not check_ua_case_client(iris_current_user.id, target_case_id):
        return response_api_error('User not entitled to unmerge alerts for the case')

    try:
        alert, _message = alerts_unmerge(alert, target_case_id=target_case_id)
        return response_api_success(AlertSchema().dump(alert))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@alerts_blueprint.post('/batch/escalate')
@ac_api_requires(Permissions.alerts_write)
def batch_escalate_alerts():
    data = request.get_json() or {}
    alert_ids_raw = data.get('alert_ids')
    if not alert_ids_raw:
        return response_api_error('No alert ids provided')

    try:
        alert_ids = parse_comma_separated_identifiers(alert_ids_raw)
    except ValueError:
        return response_api_error('Invalid alert id')

    # Customer-access gate for every requested alert. The legacy route did
    # this inside the loop; hoisting it here keeps the business layer clean
    # and prevents partial escalation before permission denial.
    for alert_id in alert_ids:
        alert = get_alert_by_id(alert_id)
        if alert and not ac_current_user_has_customer_access(alert.alert_customer_id):
            return response_api_error('User not entitled to escalate alerts for the client')

    try:
        case = alerts_batch_escalate(
            alert_ids,
            iocs_import_list=data.get('iocs_import_list'),
            assets_import_list=data.get('assets_import_list'),
            note=data.get('note'),
            import_as_event=data.get('import_as_event'),
            case_tags=data.get('case_tags'),
            case_title=data.get('case_title'),
            case_template_id=data.get('case_template_id'),
        )
        return response_api_success(CaseSchema().dump(case))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@alerts_blueprint.post('/batch/merge')
@ac_api_requires(Permissions.alerts_write)
def batch_merge_alerts():
    data = request.get_json() or {}
    target_case_id = data.get('target_case_id')
    if target_case_id is None:
        return response_api_error('No target case id provided')

    alert_ids_raw = data.get('alert_ids')
    if not alert_ids_raw:
        return response_api_error('No alert ids provided')

    try:
        alert_ids = parse_comma_separated_identifiers(alert_ids_raw)
    except ValueError:
        return response_api_error('Invalid alert id')

    if not check_ua_case_client(iris_current_user.id, target_case_id):
        return response_api_error('User not entitled to merge alerts for the case')

    for alert_id in alert_ids:
        alert = get_alert_by_id(alert_id)
        if alert and not ac_current_user_has_customer_access(alert.alert_customer_id):
            return response_api_error('User not entitled to merge alerts for the client')

    try:
        case = alerts_batch_merge(
            alert_ids,
            target_case_id=target_case_id,
            iocs_import_list=data.get('iocs_import_list'),
            assets_import_list=data.get('assets_import_list'),
            note=data.get('note'),
            import_as_event=data.get('import_as_event'),
            case_tags=data.get('case_tags'),
        )
        return response_api_success(CaseSchema().dump(case))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


# ---------------------------------------------------------------------------
# Saved alert filters — previously mounted at /api/v2/alerts-filters. Moved
# under /api/v2/alerts/filters so the entire alert surface lives under a
# single prefix.
# ---------------------------------------------------------------------------


class AlertsFiltersOperations:
    def __init__(self):
        self._schema = SavedFilterSchema()
        self._schema_many = SavedFilterSchema(many=True)

    def _load(self, request_data, **kwargs):
        return self._schema.load(request_data, **kwargs)

    def create(self):
        request_data = request.get_json()
        request_data['created_by'] = iris_current_user.id

        try:
            new_saved_filter = self._load(request_data)
            alert_filter_add(new_saved_filter)
            return response_api_created(self._schema.dump(new_saved_filter))
        except ValidationError as e:
            return response_api_error('Data error', e.messages)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def list(self):
        try:
            filter_type = request.args.get('filter_type', 'alerts')
            include_public = request.args.get('include_public', '1') == '1'

            items = alert_filter_list(
                iris_current_user,
                filter_type=filter_type,
                include_public=include_public,
            )
            return response_api_success(self._schema_many.dump(items))
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def get(self, identifier):
        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            return response_api_success(self._schema.dump(saved_filter))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def put(self, identifier):
        request_data = request.get_json() or {}
        # Pin the owner so a client can't move a filter under another user via
        # mass-assignment. See the notes in the original alerts_filters module.
        request_data['created_by'] = iris_current_user.id

        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            if saved_filter.created_by != iris_current_user.id:
                return response_api_not_found()
            new_saved_filter = self._load(request_data, instance=saved_filter, partial=True)
            alert_filter_update()
            return response_api_success(self._schema.dump(new_saved_filter))
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    @staticmethod
    def delete(identifier):
        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            if saved_filter.created_by != iris_current_user.id:
                return response_api_not_found()
            alert_filter_delete(saved_filter)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


alerts_filters_blueprint = Blueprint('alerts_filters_rest_v2', __name__, url_prefix='/filters')
alerts_filters_operations = AlertsFiltersOperations()


@alerts_filters_blueprint.post('')
@ac_api_requires()
def create_alert_filter():
    return alerts_filters_operations.create()


@alerts_filters_blueprint.get('')
@ac_api_requires()
def list_alert_filters():
    return alerts_filters_operations.list()


@alerts_filters_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_alert_filter(identifier):
    return alerts_filters_operations.get(identifier)


@alerts_filters_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_alert_filter(identifier):
    return alerts_filters_operations.put(identifier)


@alerts_filters_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_alert_filter(identifier):
    return alerts_filters_operations.delete(identifier)


alerts_blueprint.register_blueprint(alerts_filters_blueprint)
