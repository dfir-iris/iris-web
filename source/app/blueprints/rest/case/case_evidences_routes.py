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

from datetime import datetime

from marshmallow import ValidationError
from flask import Blueprint
from flask import request

from app.db import db
from app.blueprints.rest.case_comments import case_comment_update
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.case.case_rfiles_db import add_comment_to_evidence
from app.datamgmt.case.case_rfiles_db import delete_evidence_comment
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comment
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comments
from app.datamgmt.case.case_rfiles_db import get_rfile
from app.datamgmt.case.case_rfiles_db import get_rfiles
from app.datamgmt.states import get_evidences_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseEvidenceSchema
from app.schema.marshables import CommentSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.business.evidences import evidences_create
from app.business.evidences import evidences_delete
from app.business.evidences import evidences_update
from app.models.errors import BusinessProcessingError
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook


case_evidences_rest_blueprint = Blueprint('case_evidences_rest', __name__)


@case_evidences_rest_blueprint.route('/case/evidences/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/{case_identifier}/evidences')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_list_rfiles(caseid):
    crf = get_rfiles(caseid)

    ret = {
        "evidences": CaseEvidenceSchema().dump(crf, many=True),
        "state": get_evidences_state(caseid=caseid)
    }

    return response_success("", data=ret)


@case_evidences_rest_blueprint.route('/case/evidences/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_rfiles_state(caseid):
    os = get_evidences_state(caseid=caseid)
    if os:
        return response_success(data=os)
    return response_error('No evidences state for this case.')


@case_evidences_rest_blueprint.route('/case/evidences/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/{case_identifier}/evidences')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_add_rfile(caseid):
    evidence_schema = CaseEvidenceSchema()
    try:
        request_data = call_deprecated_on_preload_modules_hook('evidence_create', request.get_json(), caseid)
        evidence = evidence_schema.load(request_data)

        evidence = evidences_create(caseid, evidence)
        return response_success('Evidence added', data=evidence_schema.dump(evidence))

    except ValidationError as e:
        return response_error('Data error', data=e.messages)
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/{case_identifier}/evidences/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_get_evidence(cur_id, caseid):
    crf = get_rfile(cur_id)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    evidence_schema = CaseEvidenceSchema()
    return response_success(data=evidence_schema.dump(crf))


@case_evidences_rest_blueprint.route('/case/evidences/update/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/cases/{case_identifier}/evidences/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_edit_rfile(cur_id, caseid):
    evidence_schema = CaseEvidenceSchema()
    try:
        crf = get_rfile(cur_id)
        if not crf:
            return response_error('Invalid evidence ID for this case')

        request_data = call_deprecated_on_preload_modules_hook('evidence_update', request.get_json(), crf.case_id)
        request_data['id'] = crf.id
        evidence = evidence_schema.load(request_data, instance=crf, partial=True)

        evd = evidences_update(evidence)

        return response_success(f'Evidence {evd.filename} updated', data=evidence_schema.dump(evd))

    except ValidationError as e:
        return response_error(msg='Data error', data=e.messages)

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_evidences_rest_blueprint.route('/case/evidences/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/{case_identifier}/assets/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_delete_rfile(cur_id, caseid):
    crf = get_rfile(cur_id)
    if not crf:
        return response_error('Invalid evidence ID for this case')

    evidences_delete(crf)

    return response_success('Evidence deleted')


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>/comments/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/evidences/{evidence_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_evidence_list(cur_id, caseid):
    evidence_comments = get_case_evidence_comments(cur_id)
    if evidence_comments is None:
        return response_error('Invalid evidence ID')

    return response_success(data=CommentSchema(many=True).dump(evidence_comments))


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>/comments/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/evidences/{evidence_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_evidence_add(cur_id, caseid):
    try:
        evidence = get_rfile(cur_id)
        if not evidence:
            return response_error('Invalid evidence ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = iris_current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_evidence(evidence.id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "evidence": CaseEvidenceSchema().dump(evidence)
        }
        call_modules_hook('on_postload_evidence_commented', hook_data, caseid=caseid)

        track_activity(f"evidence \"{evidence.filename}\" commented", caseid=caseid)
        return response_success("Evidence commented", data=comment_schema.dump(comment))

    except ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/evidences/{evidence_identifier}/comments/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_evidence_get(cur_id, com_id, caseid):
    comment = get_case_evidence_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_evidence_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'tasks', caseid)


@case_evidences_rest_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_evidence_delete(cur_id, com_id, caseid):
    success, msg = delete_evidence_comment(iris_current_user.id, cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_evidence_comment_delete', com_id, caseid=caseid)

    track_activity(f"comment {com_id} on evidence {cur_id} deleted", caseid=caseid)
    return response_success(msg)
