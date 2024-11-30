# Libraries
from flask import Blueprint, request
from flask_login import current_user
from werkzeug import Response

# Common
from app.blueprints.rest.endpoints import response_api_created, response_api_deleted, response_api_error, response_api_not_found, response_api_success

# Authorization
from app.blueprints.access_controls import ac_api_requires, ac_api_return_access_denied
from app.blueprints.rest.parsing import parse_boolean, parse_comma_separated_identifiers
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel, Permissions

# Business
from app.business.cases import cases_create, cases_delete
from app.schema.marshables import CaseSchemaForAPIV2


# MARK: Blueprint -------------------------------------------------------------


# Create blueprint
bp = Blueprint('case', __name__, url_prefix='/cases')
bp_with_case_id = Blueprint('case', __name__, url_prefix='/<int:case_id>')
bp.register_blueprint(bp_with_case_id)


# MARK: Endpoints -------------------------------------------------------------


@bp.post('')
@ac_api_requires(Permissions.standard_user)
def create_case():
    """Handle creating a case"""
    
    case, _ = cases_create(request.get_json())
    return response_api_created(CaseSchemaForAPIV2().dump(case))


@bp.get('')
@ac_api_requires()
def get_cases() -> Response:
    """Get & query cases"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    case_ids_str = request.args.get('case_ids', None, type=parse_comma_separated_identifiers)
    order_by = request.args.get('order_by', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)

    case_customer_id = request.args.get('case_customer_id', None, type=str)
    case_name = request.args.get('case_name', None, type=str)
    case_description = request.args.get('case_description', None, type=str)
    case_classification_id = request.args.get('case_classification_id', None, type=int)
    case_owner_id = request.args.get('case_owner_id', None, type=int)
    case_opening_user_id = request.args.get('case_opening_user_id', None, type=int)
    case_severity_id = request.args.get('case_severity_id', None, type=int)
    case_state_id = request.args.get('case_state_id', None, type=int)
    case_soc_id = request.args.get('case_soc_id', None, type=str)
    start_open_date = request.args.get('start_open_date', None, type=str)
    end_open_date = request.args.get('end_open_date', None, type=str)
    is_open = request.args.get('is_open', None, type=parse_boolean)

    filtered_cases = get_filtered_cases(
        case_ids=case_ids_str,
        case_customer_id=case_customer_id,
        case_name=case_name,
        case_description=case_description,
        case_classification_id=case_classification_id,
        case_owner_id=case_owner_id,
        case_opening_user_id=case_opening_user_id,
        case_severity_id=case_severity_id,
        case_state_id=case_state_id,
        case_soc_id=case_soc_id,
        start_open_date=start_open_date,
        end_open_date=end_open_date,
        search_value='',
        page=page,
        per_page=per_page,
        current_user_id=current_user.id,
        sort_by=order_by,
        sort_dir=sort_dir,
        is_open=is_open
    )
    if filtered_cases is None:
        return response_api_error('Filtering error')

    cases = {
        'total': filtered_cases.total,
        # TODO should maybe really uniform all return types of paginated list and replace field cases by field data
        'data': CaseSchemaForAPIV2().dump(filtered_cases.items, many=True),
        'last_page': filtered_cases.pages,
        'current_page': filtered_cases.page,
        'next_page': filtered_cases.next_num if filtered_cases.has_next else None,
    }

    return response_api_success(data=cases)


@bp_with_case_id.get('')
@ac_api_requires()
def case_routes_get(case_id):
    """Handle retrieving case by ID."""
    
    case = get_case(case_id)
    if not case:
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_id)
    return response_api_success(CaseSchemaForAPIV2().dump(case))


@bp_with_case_id.delete('')
@ac_api_requires(Permissions.standard_user)
def case_routes_delete(case_id):
    """Handle deleting a case by ID."""
    
    if not ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_id)

    cases_delete(case_id)
    return response_api_deleted()