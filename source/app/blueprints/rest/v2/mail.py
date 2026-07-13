#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""v2 REST endpoints for mail-ingest rules + ingest log.

Server-admin gated (creating a rule = deciding what turns into an
alert/case, so this can't be a standard-user surface). The rules
table is the one operators tweak most; the ingest log is read-only
audit output.
"""

from __future__ import annotations

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.db import db
from app.models.authorization import Permissions
from app.models.mail import MailIngestLog
from app.models.mail import MailIngestRule
from app.models.mail import VALID_ACTIONS


mail_blueprint = Blueprint(
    'mail_rest_v2', __name__, url_prefix='/manage/mail')


def _serialize_rule(row: MailIngestRule) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'priority': row.priority,
        'enabled': bool(row.enabled),
        'match_subject_regex': row.match_subject_regex,
        'match_from_regex': row.match_from_regex,
        'match_to_regex': row.match_to_regex,
        'action': row.action,
        'customer_id': row.customer_id,
        'case_template_id': row.case_template_id,
        'severity_id': row.severity_id,
        'assignee_user_id': row.assignee_user_id,
        'created_by_id': row.created_by_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_log(row: MailIngestLog) -> dict:
    return {
        'message_id': row.message_id,
        'received_at': row.received_at.isoformat() if row.received_at else None,
        'outcome': row.outcome,
        'outcome_object_id': row.outcome_object_id,
        'rule_id': row.rule_id,
        'from_addr': row.from_addr,
        'subject': row.subject,
        'error': row.error,
    }


# Fields that a client can set on a rule (excludes id, created_by_id,
# timestamps — those are server-owned).
_RULE_WRITABLE_FIELDS = {
    'name', 'priority', 'enabled',
    'match_subject_regex', 'match_from_regex', 'match_to_regex',
    'action',
    'customer_id', 'case_template_id', 'severity_id', 'assignee_user_id',
}


def _apply_rule_body(row: MailIngestRule, body: dict) -> None:
    """Copy the writable fields from `body` onto `row`.

    Validates the action string against the enum-ish tuple in the
    models module. Other fields are typed by SQLAlchemy — a wrong
    type will raise on commit which the caller surfaces as a 400.
    """
    for field in _RULE_WRITABLE_FIELDS:
        if field not in body:
            continue
        value = body[field]
        if field == 'action' and value not in VALID_ACTIONS:
            raise ValueError(
                f'Unknown action {value!r}. '
                f'Expected one of {list(VALID_ACTIONS)}.'
            )
        setattr(row, field, value)


# ---------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------

@mail_blueprint.get('/rules')
@ac_api_requires(Permissions.server_administrator)
def list_rules():
    rows = (
        MailIngestRule.query
        .order_by(MailIngestRule.priority.asc(), MailIngestRule.id.asc())
        .all()
    )
    return response_api_success({
        'data': [_serialize_rule(r) for r in rows],
    })


@mail_blueprint.post('/rules')
@ac_api_requires(Permissions.server_administrator)
def create_rule():
    body = request.get_json(silent=True) or {}
    if not body.get('name'):
        return response_api_error('name is required')
    row = MailIngestRule(name=body['name'],
                         created_by_id=iris_current_user.id)
    try:
        _apply_rule_body(row, body)
        db.session.add(row)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return response_api_error(str(exc))
    return response_api_success(_serialize_rule(row))


@mail_blueprint.get('/rules/<int:rule_id>')
@ac_api_requires(Permissions.server_administrator)
def get_rule(rule_id: int):
    row = MailIngestRule.query.get(rule_id)
    if row is None:
        return response_api_not_found()
    return response_api_success(_serialize_rule(row))


@mail_blueprint.put('/rules/<int:rule_id>')
@ac_api_requires(Permissions.server_administrator)
def update_rule(rule_id: int):
    row = MailIngestRule.query.get(rule_id)
    if row is None:
        return response_api_not_found()
    body = request.get_json(silent=True) or {}
    try:
        _apply_rule_body(row, body)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return response_api_error(str(exc))
    return response_api_success(_serialize_rule(row))


@mail_blueprint.delete('/rules/<int:rule_id>')
@ac_api_requires(Permissions.server_administrator)
def delete_rule(rule_id: int):
    row = MailIngestRule.query.get(rule_id)
    if row is None:
        return response_api_not_found()
    db.session.delete(row)
    db.session.commit()
    return response_api_success({'deleted': rule_id})


# ---------------------------------------------------------------------
# Ingest log (read-only)
# ---------------------------------------------------------------------

@mail_blueprint.get('/ingest-log')
@ac_api_requires(Permissions.server_administrator)
def list_ingest_log():
    """Return the most recent ingest-log rows. `?limit=` bounded at
    500 to keep the payload small for an on-page log viewer."""
    limit = request.args.get('limit', default=100, type=int)
    limit = max(1, min(int(limit or 100), 500))
    rows = (
        MailIngestLog.query
        .order_by(MailIngestLog.received_at.desc())
        .limit(limit)
        .all()
    )
    return response_api_success({
        'data': [_serialize_log(r) for r in rows],
    })


# ---------------------------------------------------------------------
# Ad-hoc poll trigger (admin diagnostic)
# ---------------------------------------------------------------------

@mail_blueprint.post('/poll-now')
@ac_api_requires(Permissions.server_administrator)
def poll_now():
    """Run one IMAP poll immediately. Blocks on the fetch — mostly a
    diagnostic for admins tuning rules; regular polling is driven by
    the Celery beat schedule."""
    from app.iris_engine.mail.inbound import poll_inbound_mail
    result = poll_inbound_mail.apply().result
    return response_api_success(result if isinstance(result, dict) else {'result': result})
