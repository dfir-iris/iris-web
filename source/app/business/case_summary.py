#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Aggregated indicator panel for a case.

Returns the counts and excerpts the war-room graph's side sheet needs
to show "what's happening on this case right now": open task count,
top pending tasks, asset/IOC counts, severity, owner, last activity.

Kept in its own module so the war-room graph doesn't pull all of
`business.cases`.
"""

from sqlalchemy import desc, func

from app.db import db
from app.models.authorization import User
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.errors import ObjectNotFoundError


def case_summary(case_id):
    case = Cases.query.filter_by(case_id=case_id).first()
    if case is None:
        raise ObjectNotFoundError()

    from app.models.models import CaseTasks
    from app.models.assets import CaseAssets
    from app.models.iocs import Ioc
    from app.models.models import UserActivity

    task_total = (
        db.session.query(func.count(CaseTasks.id))
        .filter(CaseTasks.task_case_id == case_id)
        .scalar() or 0
    )
    task_open = (
        db.session.query(func.count(CaseTasks.id))
        .filter(CaseTasks.task_case_id == case_id,
                CaseTasks.task_status_id != None,
                CaseTasks.task_status_id != 5)  # 5 = Done in the seeded statuses
        .scalar() or 0
    )

    top_tasks = (
        db.session.query(
            CaseTasks.id, CaseTasks.task_title, CaseTasks.task_status_id,
            CaseTasks.task_assignee_id,
        )
        .filter(CaseTasks.task_case_id == case_id)
        .order_by(desc(CaseTasks.id))
        .limit(5).all()
    )

    asset_count = (
        db.session.query(func.count(CaseAssets.asset_id))
        .filter(CaseAssets.case_id == case_id)
        .scalar() or 0
    )
    ioc_count = (
        db.session.query(func.count(Ioc.ioc_id))
        .filter(Ioc.case_id == case_id)
        .scalar() or 0
    )

    event_count = (
        db.session.query(func.count(CasesEvent.event_id))
        .filter(CasesEvent.case_id == case_id)
        .scalar() or 0
    )

    last_activity = (
        UserActivity.query
        .with_entities(UserActivity.activity_date, UserActivity.activity_desc)
        .filter(UserActivity.case_id == case_id,
                UserActivity.display_in_ui == True)
        .order_by(desc(UserActivity.activity_date))
        .first()
    )

    owner = None
    if case.owner_id:
        owner_row = User.query.with_entities(
            User.id, User.user, User.name
        ).filter(User.id == case.owner_id).first()
        if owner_row:
            owner = {
                'user_id': owner_row.id,
                'user_login': owner_row.user,
                'user_name': owner_row.name,
            }

    return {
        'case_id': case.case_id,
        'name': case.name,
        'severity_id': case.severity_id,
        'state_id': case.state_id,
        'closed': case.close_date is not None,
        'owner': owner,
        'counts': {
            'tasks_total': task_total,
            'tasks_open': task_open,
            'assets': asset_count,
            'iocs': ioc_count,
            'events': event_count,
        },
        'top_tasks': [
            {
                'task_id': r.id,
                'title': r.task_title,
                'status_id': r.task_status_id,
                'assignee_id': r.task_assignee_id,
            }
            for r in top_tasks
        ],
        'last_activity': {
            'at': last_activity.activity_date.isoformat() if last_activity else None,
            'desc': last_activity.activity_desc if last_activity else None,
        } if last_activity else None,
    }
