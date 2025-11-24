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

from app.blueprints.iris_user import iris_current_user
from marshmallow.exceptions import ValidationError

from app import db
from app.models.models import Artifact, ArtifactLink
from app.models.authorization import CaseAccessLevel
from app.datamgmt.case.case_artifacts_db import add_artifact
from app.datamgmt.case.case_artifacts_db import add_artifact_link
from app.datamgmt.case.case_artifacts_db import check_artifact_type_id
from app.datamgmt.case.case_artifacts_db import get_artifacts_by_case
from app.datamgmt.case.case_artifacts_db import delete_artifact
from app.datamgmt.case.case_artifacts_db import escalate_artifact
from app.datamgmt.states import update_artifact_state
from app.schema.marshables import ArtifactSchema
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.business.errors import BusinessProcessingError
from app.business.permissions import check_current_user_has_some_case_access_stricter
from app.datamgmt.case.case_artifacts_db import get_artifact


def get_artifact_by_identifier(artifact_identifier):

    return get_artifact(artifact_identifier)


def _load(request_data):
    try:
        add_artifact_schema = ArtifactSchema()
        return add_artifact_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def create(request_json, case_identifier):

    # TODO ideally schema validation should be done before, outside the business logic in the REST API
    #      for that the hook should be called after schema validation
    request_data = call_modules_hook('on_preload_artifact_create', data=request_json, caseid=case_identifier)
    artifact = _load(request_data)

    if not check_artifact_type_id(type_id=artifact.artifact_type_id):
        raise BusinessProcessingError('Not a valid Artifact type')

    artifact, existed = add_artifact(artifact=artifact, user_id=iris_current_user.id, caseid=case_identifier)

    link_existed = add_artifact_link(artifact.artifact_id, case_identifier)

    if link_existed:
        # note: I am no big fan of returning tuples.
        # It is a code smell some type is missing, or the code is badly designed.
        return artifact, 'Artifact already exists and linked to this case'

    if not link_existed:
        artifact = call_modules_hook('on_postload_artifact_create', data=artifact, caseid=case_identifier)

    if artifact:
        track_activity(f'added artifact "{artifact.artifact_value}"', caseid=case_identifier)

        msg = 'Artifact already existed in DB. Updated with info on DB.' if existed else 'Artifact added'
        return artifact, msg

    raise BusinessProcessingError('Unable to create Artifact for internal reasons')


# TODO most probably this method should not require a case_identifier... Since the Artifact gets modified for all cases...
def update(identifier, request_json, case_identifier):

    try:
        artifact = get_artifact(identifier, caseid=case_identifier)
        if not artifact:
            raise BusinessProcessingError('Invalid Artifact ID for this case')

        # TODO ideally schema validation should be done before, outside the business logic in the REST API
        #      for that the hook should be called after schema validation
        request_data = call_modules_hook('on_preload_artifact_update', data=request_json, caseid=case_identifier)

        # validate before saving
        artifact_schema = ArtifactSchema()
        request_data['artifact_id'] = identifier
        artifact_sc = artifact_schema.load(request_data, instance=artifact, partial=True)
        artifact_sc.user_id = iris_current_user.id

        if not check_artifact_type_id(type_id=artifact_sc.artifact_type_id):
            raise BusinessProcessingError('Not a valid Artifact type')

        update_artifact_state(case_identifier)
        db.session.commit()

        artifact_sc = call_modules_hook('on_postload_artifact_update', data=artifact_sc, caseid=case_identifier)

        if artifact_sc:
            track_activity(f'updated artifact "{artifact_sc.artifact_value}"', caseid=case_identifier)
            return artifact, f'Updated artifact "{artifact_sc.artifact_value}"'

        raise BusinessProcessingError('Unable to update artifact for internal reasons')

    # TODO most probably the scope of this try catch could be reduced, this exception is probably raised only on load
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise BusinessProcessingError('Unexpected error server-side', e)

def escalate(identifier, case_identifier):

    # call_modules_hook('on_preload_artifact_delete', data=identifier, caseid=case_identifier)
    artifact = get_artifact(identifier, case_identifier)

    if not artifact:
        raise BusinessProcessingError('Not a valid artifact for this case')

    if not escalate_artifact(artifact, case_identifier):
        track_activity(f'Escalated artifact ID {artifact.artifact_value}', caseid=case_identifier)
        return f'artifact {identifier} escalated'

    # call_modules_hook('on_postload_artifact_delete', data=identifier, caseid=case_identifier)

    track_activity(f'escalated artifact "{artifact.artifact_value}"', caseid=case_identifier)
    return f'artifact {identifier} escalated'



def delete(identifier, case_identifier):

    call_modules_hook('on_preload_artifact_delete', data=identifier, caseid=case_identifier)
    artifact = get_artifact(identifier, case_identifier)

    if not artifact:
        raise BusinessProcessingError('Not a valid artifact for this case')

    if not delete_artifact(artifact, case_identifier):
        track_activity(f'unlinked artifact ID {artifact.artifact_value}', caseid=case_identifier)
        return f'artifact {identifier} unlinked'

    call_modules_hook('on_postload_artifact_delete', data=identifier, caseid=case_identifier)

    track_activity(f'deleted artifact "{artifact.artifact_value}"', caseid=case_identifier)
    return f'artifact {identifier} deleted'


def get_artifacts(case_identifier):
    check_current_user_has_some_case_access_stricter([CaseAccessLevel.read_only, CaseAccessLevel.full_access])

    return get_artifacts_by_case(case_identifier)


def build_filter_case_artifact_query(artifact_id: int = None,
                                artifact_uuid: str = None,
                                artifact_value: str = None,
                                artifact_type_id: int = None,
                                artifact_description: str = None,
                                artifact_tlp_id: int = None,
                                artifact_tags: str = None,
                                artifact_misp: str = None,
                                user_id: float = None,
                                linked_cases: float = None
                                ):
    """
    Get a list of artifacts from the database, filtered by the given parameters
    """
    conditions = []
    if artifact_id is not None:
        conditions.append(Artifact.artifact_id == artifact_id)
    if artifact_uuid is not None:
        conditions.append(Artifact.artifact_uuid == artifact_uuid)
    if artifact_value is not None:
        conditions.append(Artifact.artifact_value == artifact_value)
    if artifact_type_id is not None:
        conditions.append(Artifact.artifact_type_id == artifact_type_id)
    if artifact_description is not None:
        conditions.append(Artifact.artifact_description == artifact_description)
    if artifact_tlp_id is not None:
        conditions.append(Artifact.artifact_tlp_id == artifact_tlp_id)
    if artifact_tags is not None:
        conditions.append(Artifact.artifact_tags == artifact_tags)
    if artifact_misp is not None:
        conditions.append(Artifact.artifact_misp == artifact_misp)
    if user_id is not None:
        conditions.append(Artifact.user_id == user_id)

    query = Artifact.query.filter(*conditions)

    if linked_cases is not None:
        return query.join(ArtifactLink, Artifact.artifact_id == ArtifactLink.artifact_id).filter(ArtifactLink.case_id == linked_cases)

    return query
