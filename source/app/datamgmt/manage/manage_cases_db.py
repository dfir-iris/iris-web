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
from datetime import datetime
from datetime import date
from datetime import timedelta
from pathlib import Path

from sqlalchemy import and_, desc, asc
from sqlalchemy.orm import aliased
from functools import reduce

from app import db, app
from app.datamgmt.alerts.alerts_db import search_alert_resolution_by_name
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.authorization import has_deny_all_access_level
from app.datamgmt.states import delete_case_states
from app.models import CaseAssets, NoteRevisions
from app.models import CaseClassification
from app.models import alert_assets_association
from app.models import CaseStatus
from app.models import TaskAssignee
from app.models import NoteDirectory
from app.models import Tags
from app.models import CaseEventCategory
from app.models import CaseEventsAssets
from app.models import CaseEventsIoc
from app.models import CaseReceivedFile
from app.models import CaseTasks
from app.models import Cases
from app.models import CasesEvent
from app.models import Client
from app.models import DataStoreFile
from app.models import DataStorePath
from app.models import IocAssetLink
from app.models import IocLink
from app.models import Notes
from app.models import NotesGroup
from app.models import NotesGroupLink
from app.models import UserActivity
from app.models.alerts import AlertCaseAssociation
from app.models.authorization import CaseAccessLevel
from app.models.authorization import GroupCaseAccess
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import User
from app.models.authorization import UserCaseAccess
from app.models.authorization import UserCaseEffectiveAccess
from app.models.cases import CaseProtagonist
from app.models.cases import CaseTags
from app.models.cases import CaseState


def list_cases_id():
    res = Cases.query.with_entities(
        Cases.case_id
    ).all()

    return [r.case_id for r in res]


def list_cases_dict_unrestricted():
    owner_alias = aliased(User)
    user_alias = aliased(User)

    res = Cases.query.with_entities(
        Cases.name.label('case_name'),
        Cases.description.label('case_description'),
        Client.name.label('client_name'),
        Cases.open_date.label('case_open_date'),
        Cases.close_date.label('case_close_date'),
        Cases.soc_id.label('case_soc_id'),
        Cases.user_id.label('opened_by_user_id'),
        user_alias.user.label('opened_by'),
        Cases.owner_id,
        owner_alias.name.label('owner'),
        Cases.case_id
    ).join(
        Cases.client
    ).join(
        user_alias, and_(Cases.user_id == user_alias.id)
    ).join(
        owner_alias, and_(Cases.owner_id == owner_alias.id)
    ).order_by(
        Cases.open_date
    ).all()

    data = []
    for row in res:
        row = row._asdict()
        row['case_open_date'] = row['case_open_date'].strftime("%m/%d/%Y")
        row['case_close_date'] = row['case_close_date'].strftime("%m/%d/%Y") if row["case_close_date"] else ""
        data.append(row)

    return data


def list_cases_dict(user_id):
    owner_alias = aliased(User)
    user_alias = aliased(User)

    res = UserCaseEffectiveAccess.query.with_entities(
        Cases.name.label('case_name'),
        Cases.description.label('case_description'),
        Client.name.label('client_name'),
        Cases.open_date.label('case_open_date'),
        Cases.close_date.label('case_close_date'),
        Cases.soc_id.label('case_soc_id'),
        Cases.user_id.label('opened_by_user_id'),
        user_alias.user.label('opened_by'),
        Cases.owner_id,
        owner_alias.name.label('owner'),
        Cases.case_id,
        Cases.case_uuid,
        Cases.classification_id,
        CaseClassification.name.label('classification'),
        Cases.state_id,
        CaseState.state_name,
        UserCaseEffectiveAccess.access_level
    ).join(
        UserCaseEffectiveAccess.case
    ).join(
        Cases.client
    ).join(
        Cases.user
    ).outerjoin(
        Cases.classification
    ).outerjoin(
        Cases.state
    ).join(
        user_alias, and_(Cases.user_id == user_alias.id)
    ).join(
        owner_alias, and_(Cases.owner_id == owner_alias.id)
    ).filter(
        UserCaseEffectiveAccess.user_id == user_id
    ).order_by(
        Cases.open_date
    ).all()

    data = []
    for row in res:
        if has_deny_all_access_level(row):
            continue

        row = row._asdict()
        row['case_open_date'] = row['case_open_date'].strftime("%m/%d/%Y")
        row['case_close_date'] = row['case_close_date'].strftime("%m/%d/%Y") if row["case_close_date"] else ""
        data.append(row)

    return data


def user_list_cases_view(user_id):
    res = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.case_id
    ).filter(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.access_level != CaseAccessLevel.deny_all.value
    )).all()

    return [r.case_id for r in res]


def close_case(case_id):
    res = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    if res:
        res.close_date = datetime.utcnow()

        res.state_id = get_case_state_by_name('Closed').state_id

        db.session.commit()
        return res

    return None


def map_alert_resolution_to_case_status(case_status_id):
    if case_status_id == CaseStatus.false_positive.value:
        ares = search_alert_resolution_by_name('False Positive', exact_match=True)

    elif case_status_id == CaseStatus.true_positive_with_impact.value:
        ares = search_alert_resolution_by_name('True Positive With Impact', exact_match=True)

    elif case_status_id == CaseStatus.true_positive_without_impact.value:
        ares = search_alert_resolution_by_name('True Positive Without Impact', exact_match=True)

    elif case_status_id == CaseStatus.legitimate.value:
        ares = search_alert_resolution_by_name('Legitimate', exact_match=True)

    elif case_status_id == CaseStatus.unknown.value:
        ares = search_alert_resolution_by_name('Unknown', exact_match=True)

    else:
        ares = search_alert_resolution_by_name('Not Applicable', exact_match=True)

    if ares:
        return ares.resolution_status_id

    return None


def reopen_case(case_id):
    res = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    if res:
        res.close_date = None

        res.state_id = get_case_state_by_name('Open').state_id

        db.session.commit()
        return res

    return None


def get_case_protagonists(case_id):
    protagonists = CaseProtagonist.query.with_entities(
        CaseProtagonist.role,
        CaseProtagonist.name,
        CaseProtagonist.contact,
        User.name.label('user_name'),
        User.user.label('user_login')
    ).filter(
        CaseProtagonist.case_id == case_id
    ).outerjoin(
        CaseProtagonist.user
    ).all()

    return protagonists


def get_case_details_rt(case_id):
    case = Cases.query.filter(Cases.case_id == case_id).first()
    if case:
        owner_alias = aliased(User)
        user_alias = aliased(User)
        review_alias = aliased(User)

        res = db.session.query(Cases, Client, user_alias, owner_alias).with_entities(
            Cases.name.label('case_name'),
            Cases.description.label('case_description'),
            Cases.open_date, Cases.close_date,
            Cases.soc_id.label('case_soc_id'),
            Cases.case_id,
            Cases.case_uuid,
            Client.name.label('customer_name'),
            Cases.client_id.label('customer_id'),
            Cases.user_id.label('open_by_user_id'),
            user_alias.user.label('open_by_user'),
            Cases.owner_id,
            owner_alias.name.label('owner'),
            Cases.status_id,
            Cases.state_id,
            CaseState.state_name,
            Cases.custom_attributes,
            Cases.modification_history,
            Cases.initial_date,
            Cases.classification_id,
            CaseClassification.name.label('classification'),
            Cases.reviewer_id,
            review_alias.name.label('reviewer'),
        ).filter(and_(
            Cases.case_id == case_id
        )).join(
            user_alias, and_(Cases.user_id == user_alias.id)
        ).outerjoin(
            owner_alias, and_(Cases.owner_id == owner_alias.id)
        ).outerjoin(
            review_alias, and_(Cases.reviewer_id == review_alias.id)
        ).join(
            Cases.client,
        ).outerjoin(
            Cases.classification
        ).outerjoin(
            Cases.state
        ).first()

        if res is None:
            return None

        res = res._asdict()

        res['case_tags'] = ",".join(get_case_tags(case_id))
        res['status_name'] = CaseStatus(res['status_id']).name.replace("_", " ").title()

        res['protagonists'] = [r._asdict() for r in get_case_protagonists(case_id)]

    else:
        res = None

    return res


def delete_case(case_id):
    if not Cases.query.filter(Cases.case_id == case_id).first():
        return False

    delete_case_states(caseid=case_id)
    UserActivity.query.filter(UserActivity.case_id == case_id).delete()
    CaseReceivedFile.query.filter(CaseReceivedFile.case_id == case_id).delete()
    IocLink.query.filter(IocLink.case_id == case_id).delete()

    CaseTags.query.filter(CaseTags.case_id == case_id).delete()
    CaseProtagonist.query.filter(CaseProtagonist.case_id == case_id).delete()
    AlertCaseAssociation.query.filter(AlertCaseAssociation.case_id == case_id).delete()

    dsf_list = DataStoreFile.query.filter(DataStoreFile.file_case_id == case_id).all()

    for dsf_list_item in dsf_list:

        fln = Path(dsf_list_item.file_local_name)
        if fln.is_file():
            fln.unlink(missing_ok=True)

        db.session.delete(dsf_list_item)
    db.session.commit()

    DataStorePath.query.filter(DataStorePath.path_case_id == case_id).delete()

    da = CaseAssets.query.with_entities(CaseAssets.asset_id).filter(CaseAssets.case_id == case_id).all()
    for asset in da:
        IocAssetLink.query.filter(asset.asset_id == asset.asset_id).delete()

    CaseEventsAssets.query.filter(CaseEventsAssets.case_id == case_id).delete()
    CaseEventsIoc.query.filter(CaseEventsIoc.case_id == case_id).delete()

    CaseAssetsAlias = aliased(CaseAssets)

    # Query for CaseAssets that are not referenced in alerts and match the case_id
    assets_to_delete = db.session.query(CaseAssets).filter(
        and_(
            CaseAssets.case_id == case_id,
            ~db.session.query(alert_assets_association).filter(
                alert_assets_association.c.asset_id == CaseAssetsAlias.asset_id
            ).exists()
        )
    )

    # Delete the assets
    assets_to_delete.delete(synchronize_session='fetch')

    # Get all alerts associated with assets in the case
    alerts_to_update = db.session.query(CaseAssets).filter(CaseAssets.case_id == case_id)

    # Update case_id for the alerts
    alerts_to_update.update({CaseAssets.case_id: None}, synchronize_session='fetch')
    db.session.commit()

    # Legacy code
    NotesGroupLink.query.filter(NotesGroupLink.case_id == case_id).delete()
    NotesGroup.query.filter(NotesGroup.group_case_id == case_id).delete()

    NoteRevisions.query.filter(
        and_(
            Notes.note_case_id == case_id,
            NoteRevisions.note_id == Notes.note_id
        )
    ).delete()

    Notes.query.filter(Notes.note_case_id == case_id).delete()
    NoteDirectory.query.filter(NoteDirectory.case_id == case_id).delete()

    tasks = CaseTasks.query.filter(CaseTasks.task_case_id == case_id).all()
    for task in tasks:
        TaskAssignee.query.filter(TaskAssignee.task_id == task.id).delete()
        CaseTasks.query.filter(CaseTasks.id == task.id).delete()

    da = CasesEvent.query.with_entities(CasesEvent.event_id).filter(CasesEvent.case_id == case_id).all()
    for event in da:
        CaseEventCategory.query.filter(CaseEventCategory.event_id == event.event_id).delete()

    CasesEvent.query.filter(CasesEvent.case_id == case_id).delete()

    UserCaseAccess.query.filter(UserCaseAccess.case_id == case_id).delete()
    UserCaseEffectiveAccess.query.filter(UserCaseEffectiveAccess.case_id == case_id).delete()
    GroupCaseAccess.query.filter(GroupCaseAccess.case_id == case_id).delete()
    OrganisationCaseAccess.query.filter(OrganisationCaseAccess.case_id == case_id).delete()

    Cases.query.filter(Cases.case_id == case_id).delete()
    db.session.commit()

    return True


def build_filter_case_query(current_user_id,
                            start_open_date: str = None,
                            end_open_date: str = None,
                            case_customer_id: int = None,
                            case_ids: list = None,
                            case_name: str = None,
                            case_description: str = None,
                            case_classification_id: int = None,
                            case_owner_id: int = None,
                            case_opening_user_id: int = None,
                            case_severity_id: int = None,
                            case_state_id: int = None,
                            case_soc_id: str = None,
                            case_tags: str = None,
                            case_open_since: int = None,
                            search_value=None,
                            sort_by=None,
                            sort_dir='asc'
                            ):
    """
    Get a list of cases from the database, filtered by the given parameters
    """
    conditions = []
    if start_open_date is not None and end_open_date is not None:
        conditions.append(Cases.open_date.between(start_open_date, end_open_date))

    if case_customer_id is not None:
        conditions.append(Cases.client_id == case_customer_id)

    if case_ids is not None:
        conditions.append(Cases.case_id.in_(case_ids))

    if case_name is not None:
        conditions.append(Cases.name.ilike(f'%{case_name}%'))

    if case_description is not None:
        conditions.append(Cases.description.ilike(f'%{case_description}%'))

    if case_classification_id is not None:
        conditions.append(Cases.classification_id == case_classification_id)

    if case_owner_id is not None:
        conditions.append(Cases.owner_id == case_owner_id)

    if case_opening_user_id is not None:
        conditions.append(Cases.user_id == case_opening_user_id)

    if case_severity_id is not None:
        conditions.append(Cases.severity_id == case_severity_id)

    if case_state_id is not None:
        conditions.append(Cases.state_id == case_state_id)

    if case_soc_id is not None:
        conditions.append(Cases.soc_id == case_soc_id)

    if search_value is not None:
        conditions.append(Cases.name.like(f"%{search_value}%"))

    if case_open_since is not None:
        result = date.today() - timedelta(case_open_since)
        conditions.append(Cases.open_date == result)

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]
    conditions.append(Cases.case_id.in_(user_list_cases_view(current_user_id)))
    query = Cases.query.filter(*conditions)

    if case_tags is not None:
        return query.join(Tags, Tags.tag_title.ilike(f'%{case_tags}%')).filter(CaseTags.case_id == Cases.case_id)

    if sort_by is not None:
        order_func = desc if sort_dir == "desc" else asc

        if sort_by == 'owner':
            query = query.join(User, Cases.owner_id == User.id).order_by(order_func(User.name))

        elif sort_by == 'opened_by':
            query = query.join(User, Cases.user_id == User.id).order_by(order_func(User.name))

        elif sort_by == 'customer_name':
            query = query.join(Client, Cases.client_id == Client.client_id).order_by(order_func(Client.name))

        elif sort_by == 'state':
            query = query.join(CaseState, Cases.state_id == CaseState.state_id).order_by(order_func(CaseState.state_name))

        elif hasattr(Cases, sort_by):
            query = query.order_by(order_func(getattr(Cases, sort_by)))
    return query


def get_filtered_cases(current_user_id,
                       start_open_date: str = None,
                       end_open_date: str = None,
                       case_customer_id: int = None,
                       case_ids: list = None,
                       case_name: str = None,
                       case_description: str = None,
                       case_classification_id: int = None,
                       case_owner_id: int = None,
                       case_opening_user_id: int = None,
                       case_severity_id: int = None,
                       case_state_id: int = None,
                       case_soc_id: str = None,
                       case_open_since: int = None,
                       per_page: int = None,
                       page: int = None,
                       search_value=None,
                       sort_by=None,
                       sort_dir='asc'
                       ):
    data = build_filter_case_query(case_classification_id=case_classification_id, case_customer_id=case_customer_id, case_description=case_description,
                                   case_ids=case_ids, case_name=case_name, case_opening_user_id=case_opening_user_id, case_owner_id=case_owner_id,
                                   case_severity_id=case_severity_id, case_soc_id=case_soc_id, case_open_since=case_open_since,
                                   case_state_id=case_state_id, current_user_id=current_user_id, end_open_date=end_open_date,
                                   search_value=search_value, sort_by=sort_by, sort_dir=sort_dir, start_open_date=start_open_date)

    try:

        filtered_cases = data.paginate(page=page, per_page=per_page, error_out=False)

    except Exception as e:
        app.logger.exception(f"Error getting cases: {str(e)}")
        return None

    return filtered_cases
