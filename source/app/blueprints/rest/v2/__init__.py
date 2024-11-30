# Libraries
from flask import Blueprint, has_request_context, request
from flask_login import current_user

# Common
from app.blueprints.responses import response_error
from app.blueprints.rest.endpoints import response_api_error

# Child routes
from app.blueprints.rest.v2.case import bp as v2_api_case

# Authorization
from app.blueprints.authorization.exceptions import UnauthorizedException
from app.business.errors import BusinessProcessingError


# MARK: Blueprint -------------------------------------------------------------


# This blueprint will contain all the V2 API routes
v2_api_bp = Blueprint('v2_api', __name__, url_prefix='/api/v2')

# Register `/cases/` endpoints
v2_api_bp.register_blueprint(v2_api_case)


# MARK: Error Handling --------------------------------------------------------


# Handlers --------------------------------------------------------------------

@v2_api_bp.errorhandler(UnauthorizedException)
def handle_unauthorized(exc: UnauthorizedException):
    """Handles when `Unauthorized` is raised and returns a JSON error message."""

    error_data = {
        "user_id": exc.args[0],
        "endpoint": request.path if has_request_context() else None,
        "resource": exc.args[1],
        "action": exc.args[2],
        "resource_id": exc.args[3]
    }

    return response_error(f'Access denied while performing "{error_data["action"]}" on "{error_data["resource"]}".', data=error_data, status=403)


@v2_api_bp.errorhandler(BusinessProcessingError)
def handle_business_processing_error(exc: BusinessProcessingError):
    """Handles when `BusinessProcessingError` is raised and returns a JSON error message."""

    return response_api_error(exc.get_message(), exc.get_data())
