from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.iris_user import iris_current_user


from app.schema.marshables import SavedFilterSchema
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.alerts_filters import alert_filter_add
from app.business.alerts_filters import alert_filter_get
from app.business.alerts_filters import alert_filter_update
from app.business.alerts_filters import alert_filter_delete
from app.business.alerts_filters import alert_filter_list


class AlertsFiltersOperations:
    def __init__(self):
        self._schema = SavedFilterSchema()
        self._schema_many = SavedFilterSchema(many=True)

    def _load(self, request_data, **kwargs):
        return self._schema.load(request_data, **kwargs)

    def create(self):
        request_data = request.get_json()
        request_data["created_by"] = iris_current_user.id

        try:
            new_saved_filter = self._load(request_data)
            alert_filter_add(new_saved_filter)
            return response_api_created(self._schema.dump(new_saved_filter))

        except ValidationError as e:
            return response_api_error("Data error", e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def list(self):
        try:
            filter_type = request.args.get("filter_type", "alerts")
            include_public = request.args.get("include_public", "1") == "1"

            items = alert_filter_list(
                iris_current_user,
                filter_type=filter_type,
                include_public=include_public
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
        request_data = request.get_json()

        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            new_saved_filter = self._load(
                request_data, instance=saved_filter, partial=True
            )
            alert_filter_update()
            return response_api_success(self._schema.dump(new_saved_filter))

        except ValidationError as e:
            return response_api_error("Data error", data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    @staticmethod
    def delete(identifier):
        try:
            saved_filter = alert_filter_get(iris_current_user, identifier)
            alert_filter_delete(saved_filter)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


alerts_filters_blueprint = Blueprint(
    "alerts_filters_rest_v2", __name__, url_prefix="/alerts-filters"
)
alerts_filters_operations = AlertsFiltersOperations()


@alerts_filters_blueprint.post("")
@ac_api_requires()
def create_alert_filter():
    return alerts_filters_operations.create()


@alerts_filters_blueprint.get("")
@ac_api_requires()
def list_alert_filters():
    return alerts_filters_operations.list()


@alerts_filters_blueprint.get("/<int:identifier>")
@ac_api_requires()
def get_alert_filter(identifier):
    return alerts_filters_operations.get(identifier)


@alerts_filters_blueprint.put("/<int:identifier>")
@ac_api_requires()
def update_alert_filter(identifier):
    return alerts_filters_operations.put(identifier)


@alerts_filters_blueprint.delete("/<int:identifier>")
@ac_api_requires()
def delete_alert_filter(identifier):
    return alerts_filters_operations.delete(identifier)
