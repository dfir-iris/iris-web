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

from app.blueprints.iris_user import iris_current_user
from sqlalchemy import and_

from app import db
from app.datamgmt.states import update_artifact_state
from app.iris_engine.access_control.utils import ac_get_fast_user_cases_access
from app.models.models import CaseEventsArtifact
from app.models.cases import Cases
from app.models.models import Client
from app.models.models import Comments
from app.models.models import Artifact
from app.models.models import ArtifactAssetLink
from app.models.models import ArtifactComments
from app.models.models import ArtifactLink
# from app.models import ArtifactType
from app.models.models import IocType
from app.models.models import Tlp
from app.models.authorization import User
from app.models.models import Ioc, IocLink


def get_artifacts(caseid):
    artifacts = ArtifactLink.query.with_entities(
        Artifact.artifact_value,
        Artifact.artifact_id,
        Artifact.artifact_uuid
    ).filter(
        ArtifactLink.case_id == caseid,
        ArtifactLink.artifact_id == Artifact.artifact_id
    ).all()

    return artifacts


def get_artifacts_by_case(case_identifier) -> list[Artifact]:
    return Artifact.query.filter(
        ArtifactLink.case_id == case_identifier,
        ArtifactLink.artifact_id == Artifact.artifact_id
    ).all()


def get_artifact(artifact_id, caseid=None):
    if caseid:
        return ArtifactLink.query.with_entities(
            Artifact
        ).filter(and_(
            Artifact.artifact_id == artifact_id,
            ArtifactLink.case_id == caseid
        )).join(
            ArtifactLink.artifact
        ).first()

    return Artifact.query.filter(Artifact.artifact_id == artifact_id).first()


def update_artifact(artifact_type, artifact_tags, artifact_value, artifact_description, artifact_tlp, userid, artifact_id):
    artifact = get_artifact(artifact_id)

    if artifact:
        artifact.artifact_type = artifact_type
        artifact.artifact_tags = artifact_tags
        artifact.artifact_value = artifact_value
        artifact.artifact_description = artifact_description
        artifact.artifact_tlp_id = artifact_tlp
        artifact.user_id = userid

        db.session.commit()

    else:
        return False


def escalate_artifact(artifact, caseid):
    new_ioc = Ioc(
        ioc_value=artifact.artifact_value,
        ioc_type_id=artifact.artifact_type_id,
        ioc_description=f"Escalated from artifact: {artifact.artifact_description}" if artifact.artifact_description else "",
        ioc_tags=artifact.artifact_tags,
        user_id=artifact.user_id,
        ioc_tlp_id=artifact.artifact_tlp_id,
        custom_attributes=artifact.custom_attributes,
        #ioc_enrichment=artifact.artifact_enrichment,
        #modification_history=artifact.modification_history
    )
    
    # Add to session and commit to get the ID
    db.session.add(new_ioc)
    db.session.commit()
    # return True
    
    # Create link to the case
    ioc_link = IocLink(
        ioc_id=new_ioc.ioc_id,
        case_id=caseid
    )
    db.session.add(ioc_link)
    db.session.commit()
    return True


def delete_artifact(artifact, caseid):
    with db.session.begin_nested():
        ArtifactLink.query.filter(
            and_(
                ArtifactLink.artifact_id == artifact.artifact_id,
                ArtifactLink.case_id == caseid
            )
        ).delete()

        res = ArtifactLink.query.filter(
                ArtifactLink.artifact_id == artifact.artifact_id,
                ).all()

        if res:
            return False

        ArtifactAssetLink.query.filter(
            ArtifactAssetLink.artifact_id == artifact.artifact_id
        ).delete()

        CaseEventsArtifact.query.filter(
            CaseEventsArtifact.artifact_id == artifact.artifact_id
        ).delete()

        com_ids = ArtifactComments.query.with_entities(
            ArtifactComments.comment_id
        ).filter(
            ArtifactComments.comment_artifact_id == artifact.artifact_id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        ArtifactComments.query.filter(ArtifactComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        db.session.delete(artifact)

        update_artifact_state(caseid=caseid)

    return True


def get_detailed_artifacts(caseid):
    detailed_artifacts = (ArtifactLink.query.with_entities(
        Artifact.artifact_id,
        Artifact.artifact_uuid,
        Artifact.artifact_value,
        Artifact.artifact_type_id,
        IocType.type_name.label('ioc_type'),
        # ArtifactType.type_name.label('artifact_type'),
        Artifact.artifact_type_id,
        Artifact.artifact_description,
        Artifact.artifact_tags,
        Artifact.artifact_misp,
        Tlp.tlp_name,
        Tlp.tlp_bscolor,
        Artifact.artifact_tlp_id
    ).filter(
        and_(ArtifactLink.case_id == caseid,
             ArtifactLink.artifact_id == Artifact.artifact_id)
    ).join(ArtifactLink.artifact)
     .join(Artifact.artifact_type)
     .outerjoin(Artifact.tlp)
    #  .order_by(ArtifactType.type_name).all())
     .order_by(IocType.type_name).all())

    return detailed_artifacts


def get_artifact_links(artifact_id, caseid):
    search_condition = and_(Cases.case_id.in_([]))

    user_search_limitations = ac_get_fast_user_cases_access(iris_current_user.id)
    if user_search_limitations:
        search_condition = and_(Cases.case_id.in_(user_search_limitations))

    artifact_link = (ArtifactLink.query.with_entities(
        Cases.case_id,
        Cases.name.label('case_name'),
        Client.name.label('client_name')
    ).filter(and_(
        ArtifactLink.artifact_id == artifact_id,
        ArtifactLink.case_id != caseid,
        search_condition)
    ).join(ArtifactLink.case)
     .join(Cases.client)
     .all())

    return artifact_link


def find_artifact(artifact_value, artifact_type_id):
    artifact = Artifact.query.filter(Artifact.artifact_value == artifact_value,
                           Artifact.artifact_type_id == artifact_type_id).first()

    return artifact


def add_artifact(artifact: Artifact, user_id, caseid):
    if not artifact:
        return None, False

    artifact.user_id = user_id

    db_artifact = find_artifact(artifact.artifact_value, artifact.artifact_type_id)

    if not db_artifact:
        db.session.add(artifact)

        update_artifact_state(caseid=caseid)
        db.session.commit()
        return artifact, False

    else:
        # IoC already exists
        return db_artifact, True


def find_artifact_link(*, artifact_id:int, caseid:int):
    db_link = ArtifactLink.query.filter(
        ArtifactLink.case_id == caseid,
        ArtifactLink.artifact_id == artifact_id
    ).first()

    return db_link

def add_artifact_link(artifact_id, caseid):
    db_link = find_artifact_link(artifact_id=artifact_id, caseid=caseid)
    if db_link:
        # Link already exists
        return True
    else:
        link = ArtifactLink()
        link.case_id = caseid
        link.artifact_id = artifact_id

        db.session.add(link)
        db.session.commit()

        return False


def get_artifact_types_list():
    # artifact_types = ArtifactType.query.with_entities(
    #     ArtifactType.type_id,
    #     ArtifactType.type_name,
    #     ArtifactType.type_description,
    #     ArtifactType.type_taxonomy,
    #     ArtifactType.type_validation_regex,
    #     ArtifactType.type_validation_expect,
    # ).all()
    artifact_types = IocType.query.with_entities(
        IocType.type_id,
        IocType.type_name,
        IocType.type_description,
        IocType.type_taxonomy,
        IocType.type_validation_regex,
        IocType.type_validation_expect,
    ).all()

    l_types = [row._asdict() for row in artifact_types]
    return l_types


def add_artifact_type(name:str, description:str, taxonomy:str):
    # artifactt = ArtifactType(type_name=name,
    #                type_description=description,
    #                type_taxonomy=taxonomy
    #             )
    artifactt = IocType(type_name=name,
                   type_description=description,
                   type_taxonomy=taxonomy
                )

    db.session.add(artifactt)
    db.session.commit()
    return artifactt


def check_artifact_type_id(type_id: int):
    # type_id = ArtifactType.query.filter(
    #     ArtifactType.type_id == type_id
    # ).first()
    type_id = IocType.query.filter(
        IocType.type_id == type_id
    ).first()

    return type_id


def get_artifact_type_id(type_name: str):
    # type_id = ArtifactType.query.filter(
    #     ArtifactType.type_name == type_name
    # ).first()
    type_id = IocType.query.filter(
        IocType.type_name == type_name
    ).first()

    return type_id if type_id else None


def get_tlps():
    return [(tlp.tlp_id, tlp.tlp_name) for tlp in Tlp.query.all()]


def get_tlps_dict():
    tlpDict = {}
    for tlp in Tlp.query.all():
        tlpDict[tlp.tlp_name]=tlp.tlp_id 
    return tlpDict


def get_case_artifact_comments(artifact_id):
    return Comments.query.filter(
        ArtifactComments.comment_artifact_id == artifact_id
    ).with_entities(
        Comments
    ).join(
        ArtifactComments,
        Comments.comment_id == ArtifactComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_artifact(artifact_id, comment_id):
    ec = ArtifactComments()
    ec.comment_artifact_id = artifact_id
    ec.comment_id = comment_id

    db.session.add(ec)
    db.session.commit()


def get_case_artifacts_comments_count(artifacts_list):
    return ArtifactComments.query.filter(
        ArtifactComments.comment_artifact_id.in_(artifacts_list)
    ).with_entities(
        ArtifactComments.comment_artifact_id,
        ArtifactComments.comment_id
    ).group_by(
        ArtifactComments.comment_artifact_id,
        ArtifactComments.comment_id
    ).all()


def get_case_artifact_comment(artifact_id, comment_id):
    return (ArtifactComments.query.filter(
        ArtifactComments.comment_artifact_id == artifact_id,
        ArtifactComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(ArtifactComments.comment)
            .join(Comments.user).first())


def delete_artifact_comment(artifact_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == iris_current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    ArtifactComments.query.filter(
        ArtifactComments.comment_artifact_id == artifact_id,
        ArtifactComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"

def get_artifact_by_value(artifact_value, caseid=None):
    if caseid:
        return ArtifactLink.query.with_entities(
            Artifact
        ).filter(and_(
            Artifact.artifact_value == artifact_value,
            ArtifactLink.case_id == caseid
        )).join(
            ArtifactLink.artifact
        ).first()

    return Artifact.query.filter(Artifact.artifact_value == artifact_value).first()
