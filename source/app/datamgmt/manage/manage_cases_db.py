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
from typing import Any

from sqlalchemy import and_, or_, cast, String
from sqlalchemy.orm import aliased
from functools import reduce

from app.db import db
from app.datamgmt.alerts.alerts_db import search_alert_resolution_by_name
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.conversions import convert_sort_direction
from app.datamgmt.authorization import has_deny_all_access_level
from app.datamgmt.states import delete_case_states
from app.models.models import NoteRevisions
from app.models.assets import alert_assets_association, CaseAssets
from app.models.models import TaskAssignee
from app.models.models import NoteDirectory
from app.models.models import Tags
from app.models.models import CaseEventCategory
from app.models.models import CaseEventsAssets
from app.models.models import CaseEventsIoc
from app.models.evidences import CaseReceivedFile
from app.models.models import CaseTasks
from app.models.cases import Cases, CaseStatus, CaseClassification
from app.models.cases import CasesEvent
from app.models.customers import Client
from app.models.models import DataStoreFile
from app.models.models import DataStorePath
from app.models.models import IocAssetLink
from app.models.models import Notes
from app.models.models import NotesGroup
from app.models.models import NotesGroupLink
from app.models.models import UserActivity
from app.models.alerts import AlertCaseAssociation
from app.models.comments import Comments, IocComments, AssetComments
from app.models.authorization import CaseAccessLevel
from app.models.authorization import GroupCaseAccess
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import User
from app.models.authorization import UserCaseAccess
from app.models.authorization import UserCaseEffectiveAccess
from app.models.iocs import Ioc
from app.models.cases import CaseProtagonist
from app.models.cases import CaseTags
from app.models.cases import CaseState
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.case.case_rfiles_db import delete_evidences_comments_in_case
from app.datamgmt.case.case_notes_db import delete_notes_comments_in_case
from app.datamgmt.case.case_tasks_db import delete_tasks_comments_in_case
from app.datamgmt.case.case_events_db import delete_events_comments_in_case


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


def _delete_iocs(case_identifier):
    # IoCs are shared between cases and alerts via `alert_iocs_association`.
    # If we bulk-delete every IoC with `case_id = X` we hit the FK
    # constraint as soon as one of them is still referenced from an
    # alert (legitimate state: the IoC came in via an alert that wasn't
    # merged into this case, or the case is being deleted but the alert
    # survives). Mirror the partitioning `_delete_assets` already does:
    #   - IoCs not referenced by any alert  → fully delete (with their
    #     comments and link tables);
    #   - IoCs still referenced by an alert → detach by clearing
    #     `case_id` so the case-level FK no longer pins them, but the
    #     alert-side association stays intact.
    from app.models.iocs import alert_iocs_association

    referenced_subq = db.session.query(alert_iocs_association.c.ioc_id).filter(
        alert_iocs_association.c.ioc_id == Ioc.ioc_id
    ).exists()

    deletable_ids = [
        row.ioc_id
        for row in db.session.query(Ioc.ioc_id).filter(
            Ioc.case_id == case_identifier,
            ~referenced_subq,
        ).all()
    ]

    if deletable_ids:
        com_ids = [
            c.comment_id
            for c in IocComments.query.with_entities(IocComments.comment_id).filter(
                IocComments.comment_ioc_id.in_(deletable_ids)
            ).all()
        ]
        if com_ids:
            IocComments.query.filter(IocComments.comment_id.in_(com_ids)).delete(
                synchronize_session=False)
            Comments.query.filter(Comments.comment_id.in_(com_ids)).delete(
                synchronize_session=False)

        # IocAssetLink + CaseEventsIoc rows for these IoCs are scoped to
        # this case (link tables don't survive the case anyway), but
        # CaseEventsIoc filtering at the caller level only covers the
        # `case_id` column. Belt-and-braces: clear them by ioc_id too so
        # we never hit an "ioc still referenced" FK from a stray link.
        IocAssetLink.query.filter(IocAssetLink.ioc_id.in_(deletable_ids)).delete(
            synchronize_session=False)
        CaseEventsIoc.query.filter(CaseEventsIoc.ioc_id.in_(deletable_ids)).delete(
            synchronize_session=False)

        Ioc.query.filter(Ioc.ioc_id.in_(deletable_ids)).delete(
            synchronize_session=False)

    # Anything left behind belonged to alerts too — detach from the case
    # so the next `Cases.query.filter(...).delete()` doesn't fail on
    # `ioc.case_id → cases.case_id`.
    Ioc.query.filter(Ioc.case_id == case_identifier).update(
        {Ioc.case_id: None}, synchronize_session=False)


def _delete_assets(case_identifier):
    com_ids = AssetComments.query.with_entities(
        AssetComments.comment_id
    ).join(CaseAssets).filter(
        AssetComments.comment_asset_id == CaseAssets.asset_id,
        CaseAssets.case_id == case_identifier
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    AssetComments.query.filter(AssetComments.comment_id.in_(com_ids)).delete()
    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

    CaseAssetsAlias = aliased(CaseAssets)

    # Query for CaseAssets that are not referenced in alerts and match the case_id
    assets_to_delete = db.session.query(CaseAssets).filter(
        and_(
            CaseAssets.case_id == case_identifier,
            ~db.session.query(alert_assets_association).filter(
                alert_assets_association.c.asset_id == CaseAssetsAlias.asset_id
            ).exists()
        )
    )
    # Delete the assets
    assets_to_delete.delete(synchronize_session='fetch')


def _delete_evidences(case_identifier):
    delete_evidences_comments_in_case(case_identifier)
    CaseReceivedFile.query.filter(CaseReceivedFile.case_id == case_identifier).delete()


def _delete_notes(case_identifier):
    delete_notes_comments_in_case(case_identifier)
    # Legacy code
    NotesGroupLink.query.filter(NotesGroupLink.case_id == case_identifier).delete()
    NotesGroup.query.filter(NotesGroup.group_case_id == case_identifier).delete()
    NoteRevisions.query.filter(
        and_(
            Notes.note_case_id == case_identifier,
            NoteRevisions.note_id == Notes.note_id
        )
    ).delete()
    Notes.query.filter(Notes.note_case_id == case_identifier).delete()
    NoteDirectory.query.filter(NoteDirectory.case_id == case_identifier).delete()


def _delete_tasks(case_identifier):
    delete_tasks_comments_in_case(case_identifier)
    tasks = CaseTasks.query.filter(CaseTasks.task_case_id == case_identifier).all()
    for task in tasks:
        TaskAssignee.query.filter(TaskAssignee.task_id == task.id).delete()
        CaseTasks.query.filter(CaseTasks.id == task.id).delete()


def _delete_events(case_identifier):
    delete_events_comments_in_case(case_identifier)
    da = CasesEvent.query.with_entities(CasesEvent.event_id).filter(CasesEvent.case_id == case_identifier).all()
    for event in da:
        CaseEventCategory.query.filter(CaseEventCategory.event_id == event.event_id).delete()
    CasesEvent.query.filter(CasesEvent.case_id == case_identifier).delete()


def delete_case(case_id):
    if not Cases.query.filter(Cases.case_id == case_id).first():
        return False

    delete_case_states(caseid=case_id)
    UserActivity.query.filter(UserActivity.case_id == case_id).delete()
    _delete_evidences(case_id)
    _delete_iocs(case_id)

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

    _delete_assets(case_id)

    # Get all alerts associated with assets in the case
    alerts_to_update = db.session.query(CaseAssets).filter(CaseAssets.case_id == case_id)

    # Update case_id for the alerts
    alerts_to_update.update({CaseAssets.case_id: None}, synchronize_session='fetch')
    db.session.commit()

    _delete_notes(case_id)
    _delete_tasks(case_id)

    _delete_events(case_id)

    UserCaseAccess.query.filter(UserCaseAccess.case_id == case_id).delete()
    UserCaseEffectiveAccess.query.filter(UserCaseEffectiveAccess.case_id == case_id).delete()
    GroupCaseAccess.query.filter(GroupCaseAccess.case_id == case_id).delete()
    OrganisationCaseAccess.query.filter(OrganisationCaseAccess.case_id == case_id).delete()

    Cases.query.filter(Cases.case_id == case_id).delete()
    db.session.commit()

    return True


# TODO is it really necessary to have both case_name and search_value
#      as of now, it seems case_name does a case.name.ilike, whereas search_value does a case.name.like
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
                            sort_dir='asc',
                            is_open: bool=None,
                            quick_search: str=None
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

    quick_search_term = quick_search.strip() if isinstance(quick_search, str) else None
    if quick_search_term:
        # Case IDs are prefixed into the title at creation time (e.g. "#42 - Foo"),
        # so an ILIKE on Cases.name already catches numeric matches via the prefix.
        conditions.append(or_(
            Cases.name.ilike(f"%{quick_search_term}%"),
            Client.name.ilike(f"%{quick_search_term}%")
        ))

    if case_open_since is not None:
        result = date.today() - timedelta(case_open_since)
        conditions.append(Cases.open_date == result)

    if is_open is not None:

        if is_open:
            conditions.append(Cases.close_date.is_(None))
        else:
            conditions.append(Cases.close_date.is_not(None))

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]
    conditions.append(Cases.case_id.in_(user_list_cases_view(current_user_id)))
    base_query = Cases.query
    # quick_search references Client.name, so make sure the table is joined
    # before the filter is applied. Use an outer join so cases without a
    # customer are still considered for the name/id match.
    if quick_search_term:
        base_query = base_query.outerjoin(Client, Cases.client_id == Client.client_id)
    query = base_query.filter(*conditions)

    if case_tags is not None:
        return query.join(Tags, Tags.tag_title.ilike(f'%{case_tags}%')).filter(CaseTags.case_id == Cases.case_id)

    if sort_by is not None:
        order_func = convert_sort_direction(sort_dir)

        if sort_by == 'owner':
            query = query.join(User, Cases.owner_id == User.id).order_by(order_func(User.name))

        elif sort_by == 'opened_by':
            query = query.join(User, Cases.user_id == User.id).order_by(order_func(User.name))

        elif sort_by == 'customer_name':
            if quick_search_term:
                # Client is already joined via the quick_search outer join; just order by it.
                query = query.order_by(order_func(Client.name))
            else:
                query = query.join(Client, Cases.client_id == Client.client_id).order_by(order_func(Client.name))

        elif sort_by == 'state':
            query = query.join(CaseState, Cases.state_id == CaseState.state_id).order_by(order_func(CaseState.state_name))

        elif hasattr(Cases, sort_by):
            query = query.order_by(order_func(getattr(Cases, sort_by)))
    return query


def get_filtered_cases(current_user_id,
                       pagination_parameters: PaginationParameters,
                       start_open_date: str | None = None,
                       end_open_date: str | None = None,
                       case_customer_id: int | None = None,
                       case_ids: list[int] | None = None,
                       case_name: str | None = None,
                       case_description: str | None = None,
                       case_classification_id: int | None = None,
                       case_owner_id: int | None = None,
                       case_opening_user_id: int | None = None,
                       case_severity_id: int | None = None,
                       case_state_id: int | None = None,
                       case_soc_id: str | None = None,
                       case_open_since: int | None = None,
                       search_value: str | None = None,
                       is_open: bool | None = None,
                       advanced_filters: list[dict[str, Any]] | None = None,
                       advanced_logic: str = 'and',
                       quick_search: str | None = None
                       ):
    kwargs: dict[str, Any] = {
        'current_user_id': current_user_id,
        'sort_by': pagination_parameters.get_order_by(),
        'sort_dir': pagination_parameters.get_direction()
    }

    if start_open_date is not None:
        kwargs['start_open_date'] = start_open_date
    if end_open_date is not None:
        kwargs['end_open_date'] = end_open_date

    if case_customer_id is not None:
        kwargs['case_customer_id'] = case_customer_id

    if case_ids is not None:
        kwargs['case_ids'] = case_ids

    if case_name is not None:
        kwargs['case_name'] = case_name

    if case_description is not None:
        kwargs['case_description'] = case_description

    if case_classification_id is not None:
        kwargs['case_classification_id'] = case_classification_id

    if case_owner_id is not None:
        kwargs['case_owner_id'] = case_owner_id

    if case_opening_user_id is not None:
        kwargs['case_opening_user_id'] = case_opening_user_id

    if case_severity_id is not None:
        kwargs['case_severity_id'] = case_severity_id

    if case_state_id is not None:
        kwargs['case_state_id'] = case_state_id

    if case_soc_id is not None:
        kwargs['case_soc_id'] = case_soc_id

    if case_open_since is not None:
        kwargs['case_open_since'] = case_open_since

    if search_value is not None:
        kwargs['search_value'] = search_value

    if quick_search is not None:
        kwargs['quick_search'] = quick_search

    if is_open is not None:
        kwargs['is_open'] = is_open

    query = build_filter_case_query(**kwargs)

    if advanced_filters:
        adv_conditions = []
        joined_client = False
        joined_state = False
        joined_owner = False

        for f in advanced_filters:
            field_id = f.get('fieldId')
            operation = f.get('operation')
            value = f.get('value', '')

            if not isinstance(field_id, str) or not isinstance(operation, str) or not isinstance(value, str):
                continue

            field_expr: Any = None

            if field_id == 'title':
                field_expr = Cases.name
            elif field_id == 'case_id':
                field_expr = cast(Cases.case_id, String)
            elif field_id == 'outcome':
                field_expr = Cases.closing_note
            elif field_id == 'open_date':
                field_expr = cast(Cases.open_date, String)
            elif field_id == 'classification':
                field_expr = cast(Cases.classification_id, String)
            elif field_id == 'customer':
                if not joined_client:
                    query = query.join(Client, Cases.client_id == Client.client_id)
                    joined_client = True
                field_expr = Client.name
            elif field_id == 'state':
                if not joined_state:
                    query = query.join(CaseState, Cases.state_id == CaseState.state_id)
                    joined_state = True
                field_expr = CaseState.state_name
            elif field_id == 'owner':
                if not joined_owner:
                    query = query.join(User, Cases.owner_id == User.id)
                    joined_owner = True
                field_expr = User.user

            if field_expr is None:
                continue

            op = operation.lower()

            if op == 'empty':
                adv_conditions.append(or_(field_expr.is_(None), field_expr == ''))
                continue
            if op == 'not_empty':
                adv_conditions.append(and_(field_expr.is_not(None), field_expr != ''))
                continue

            if op == 'equals':
                adv_conditions.append(field_expr == value)
            elif op == 'not':
                adv_conditions.append(field_expr != value)
            elif op == 'starts_with':
                adv_conditions.append(field_expr.ilike(f'{value}%'))
            elif op == 'not_starts_with':
                adv_conditions.append(~field_expr.ilike(f'{value}%'))
            elif op == 'contains':
                adv_conditions.append(field_expr.ilike(f'%{value}%'))
            elif op == 'not_contains':
                adv_conditions.append(~field_expr.ilike(f'%{value}%'))
            elif op == 'ends_with':
                adv_conditions.append(field_expr.ilike(f'%{value}'))
            elif op == 'not_ends_with':
                adv_conditions.append(~field_expr.ilike(f'%{value}'))

        if adv_conditions:
            if (advanced_logic or 'and').lower() == 'or':
                query = query.filter(or_(*adv_conditions))
            else:
                query = query.filter(and_(*adv_conditions))

    return query.paginate(page=pagination_parameters.get_page(),
                          per_page=pagination_parameters.get_per_page(),
                          error_out=False)
