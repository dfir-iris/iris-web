"""v2 cases-filters endpoints.

Thin re-export of the alerts-filters business layer with `filter_type`
defaulted to ``cases`` so the UI's cases overview page can save / list
/ delete its own filter presets without colliding with the alerts
ones. The underlying `SavedFilter` row stores the type as free text,
so this is a routing concern only — no new model / no new business
logic.

We mount the same five verbs as alerts-filters (list / get / create /
update / delete) and apply identical authorisation: a saved filter is
visible to its owner when private, or to everyone when public. The
business layer already enforces this.
"""
from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.iris_user import iris_current_user
from app.business.alerts_filters import alert_filter_add
from app.business.alerts_filters import alert_filter_delete
from app.business.alerts_filters import alert_filter_get
from app.business.alerts_filters import alert_filter_list
from app.business.alerts_filters import alert_filter_update
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import SavedFilterSchema


class CasesFiltersOperations:
    def __init__(self):
        self._schema = SavedFilterSchema()
        self._schema_many = SavedFilterSchema(many=True)

    def _load(self, request_data, **kwargs):
        return self._schema.load(request_data, **kwargs)

    def create(self):
        # Always stamp filter_type='cases' even if the client omitted
        # it — the cases endpoint owns this namespace. Also force
        # `created_by` from the session user so a malicious client
        # can't impersonate another owner.
        request_data = request.get_json() or {}
        request_data['created_by'] = iris_current_user.id
        request_data.setdefault('filter_type', 'cases')
        if request_data.get('filter_type') != 'cases':
            return response_api_error("filter_type must be 'cases' for this endpoint")

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
            include_public = request.args.get('include_public', '1') == '1'
            items = alert_filter_list(
                iris_current_user,
                filter_type='cases',
                include_public=include_public,
            )
            return response_api_success(self._schema_many.dump(items))
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def get(self, identifier):
        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            if saved_filter.filter_type != 'cases':
                return response_api_not_found()
            return response_api_success(self._schema.dump(saved_filter))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def put(self, identifier):
        request_data = request.get_json() or {}
        # The filter_type can't be moved out of 'cases' through this
        # endpoint — it would be a no-op route swap from the user's
        # perspective and a footgun for the alerts UI.
        request_data['filter_type'] = 'cases'

        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            if saved_filter.filter_type != 'cases':
                return response_api_not_found()
            new_saved_filter = self._load(
                request_data, instance=saved_filter, partial=True
            )
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
            if saved_filter.filter_type != 'cases':
                return response_api_not_found()
            alert_filter_delete(saved_filter)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


cases_filters_blueprint = Blueprint(
    'cases_filters_rest_v2', __name__, url_prefix='/cases-filters'
)
cases_filters_operations = CasesFiltersOperations()


@cases_filters_blueprint.post('')
@ac_api_requires()
def create_case_filter():
    return cases_filters_operations.create()


@cases_filters_blueprint.get('')
@ac_api_requires()
def list_case_filters():
    return cases_filters_operations.list()


@cases_filters_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_filter(identifier):
    return cases_filters_operations.get(identifier)


@cases_filters_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_case_filter(identifier):
    return cases_filters_operations.put(identifier)


@cases_filters_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_filter(identifier):
    return cases_filters_operations.delete(identifier)
