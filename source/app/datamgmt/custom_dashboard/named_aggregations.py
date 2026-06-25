"""Post-query named aggregations for custom dashboards.

The query engine in query_engine.py is declarative: table.column + whitelisted
SQL aggregations + whitelisted filter operators. Some statistics (MTTD, MTTR,
false-positive rate, escalation rate, sliding-window alert counts) cannot be
expressed as a single SQL aggregation because they walk JSON modification
history rows or compose two counts. They live here as Python helpers that the
render endpoint resolves when a widget references table=='computed'.

A widget that uses a named aggregation looks like:

    {
        "name": "Mean time to detect",
        "chart_type": "number",
        "fields": [{"table": "computed", "column": "mttd_seconds", "alias": "mttd_seconds"}]
    }

The registry is intentionally small and additive: future named aggregations
register a callable(timeframe, filters, scope) -> Optional[float]. The engine
never touches user-supplied identifiers; only registered names resolve.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from flask_login import current_user
from sqlalchemy import and_, func, or_, select

from app import db
from app.datamgmt.manage.manage_access_control_db import get_user_clients_id
from app.iris_engine.access_control.utils import ac_current_user_has_permission, ac_get_fast_user_cases_access
from app.models.alerts import Alert, AlertCaseAssociation, AlertResolutionStatus, AlertStatus
from app.models.authorization import Permissions
from app.models.cases import Cases


class NamedAggregationError(Exception):
    pass


@dataclass
class ComputedFilters:
    customer_id: Optional[int] = None
    severity_id: Optional[int] = None
    case_status_id: Optional[int] = None
    window: Optional[str] = None


def _normalize_history(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    entries: List[Tuple[datetime, str]] = []
    for ts_raw, payload in value.items():
        ts = _parse_datetime(ts_raw)
        if ts is None:
            continue
        if isinstance(payload, dict):
            action = str(payload.get('action') or payload.get('event') or payload.get('description') or '').lower()
        else:
            action = str(payload or '').lower()
        entries.append((ts, action))
    entries.sort(key=lambda item: item[0])
    return [{'timestamp': ts, 'action': action} for ts, action in entries]


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _average_seconds(deltas: Iterable[timedelta]) -> Optional[float]:
    deltas = [d for d in deltas if isinstance(d, timedelta) and d.total_seconds() >= 0]
    if not deltas:
        return None
    total = sum((d.total_seconds() for d in deltas), 0.0)
    return total / len(deltas)


def _apply_access_filter_to_alert_query(stmt):
    if ac_current_user_has_permission(Permissions.server_administrator):
        return stmt
    user_id = getattr(current_user, 'id', None)
    if not user_id:
        return stmt.where(Alert.alert_id == -1)
    client_ids = get_user_clients_id(user_id) or []
    case_ids = ac_get_fast_user_cases_access(user_id) or []
    conditions = []
    if client_ids:
        conditions.append(Alert.alert_customer_id.in_(client_ids))
    if case_ids:
        sub = select(AlertCaseAssociation.alert_id).where(AlertCaseAssociation.case_id.in_(case_ids))
        conditions.append(Alert.alert_id.in_(sub))
    if not conditions:
        return stmt.where(Alert.alert_id == -1)
    if len(conditions) == 1:
        return stmt.where(conditions[0])
    return stmt.where(or_(*conditions))


def _apply_access_filter_to_case_query(stmt):
    if ac_current_user_has_permission(Permissions.server_administrator):
        return stmt
    user_id = getattr(current_user, 'id', None)
    if not user_id:
        return stmt.where(Cases.case_id == -1)
    case_ids = ac_get_fast_user_cases_access(user_id) or []
    if not case_ids:
        return stmt.where(Cases.case_id == -1)
    return stmt.where(Cases.case_id.in_(case_ids))


def _apply_timeframe(stmt, column, timeframe: Tuple[Optional[datetime], Optional[datetime]]):
    start, end = timeframe
    if start is not None:
        stmt = stmt.where(column >= start)
    if end is not None:
        stmt = stmt.where(column <= end)
    return stmt


def _apply_alert_filters(stmt, filters: ComputedFilters):
    if filters.customer_id is not None:
        stmt = stmt.where(Alert.alert_customer_id == filters.customer_id)
    if filters.severity_id is not None:
        stmt = stmt.where(Alert.alert_severity_id == filters.severity_id)
    return stmt


def _apply_case_filters(stmt, filters: ComputedFilters):
    if filters.customer_id is not None:
        stmt = stmt.where(Cases.client_id == filters.customer_id)
    if filters.severity_id is not None:
        stmt = stmt.where(Cases.severity_id == filters.severity_id)
    if filters.case_status_id is not None:
        stmt = stmt.where(Cases.state_id == filters.case_status_id)
    return stmt


def _mttd_seconds(timeframe, filters: ComputedFilters) -> Optional[float]:
    stmt = select(Cases.modification_history, Cases.open_date)
    stmt = _apply_case_filters(stmt, filters)
    stmt = _apply_timeframe(stmt, Cases.open_date, timeframe)
    stmt = _apply_access_filter_to_case_query(stmt)
    deltas: List[timedelta] = []
    for history, open_date in db.session.execute(stmt).all():
        if open_date is None:
            continue
        entries = _normalize_history(history)
        transition_ts = next((e['timestamp'] for e in entries if 'in progress' in e['action'] or 'in_progress' in e['action']), None)
        if transition_ts is None:
            continue
        deltas.append(transition_ts - open_date)
    return _average_seconds(deltas)


def _mttr_seconds(timeframe, filters: ComputedFilters) -> Optional[float]:
    stmt = select(Cases.modification_history, Cases.open_date)
    stmt = _apply_case_filters(stmt, filters)
    stmt = _apply_timeframe(stmt, Cases.open_date, timeframe)
    stmt = _apply_access_filter_to_case_query(stmt)
    deltas: List[timedelta] = []
    for history, open_date in db.session.execute(stmt).all():
        if open_date is None:
            continue
        entries = _normalize_history(history)
        transition_ts = next((e['timestamp'] for e in entries if 'closed' in e['action'] or 'resolved' in e['action']), None)
        if transition_ts is None:
            continue
        deltas.append(transition_ts - open_date)
    return _average_seconds(deltas)


def _false_positive_rate(timeframe, filters: ComputedFilters) -> Optional[float]:
    fp_status = db.session.execute(
        select(AlertResolutionStatus.resolution_status_id)
        .where(func.lower(AlertResolutionStatus.resolution_status_name) == 'false positive')
    ).scalar_one_or_none()

    base_stmt = select(func.count(Alert.alert_id))
    base_stmt = _apply_alert_filters(base_stmt, filters)
    base_stmt = _apply_timeframe(base_stmt, Alert.alert_creation_time, timeframe)
    base_stmt = _apply_access_filter_to_alert_query(base_stmt)
    total = db.session.execute(base_stmt).scalar() or 0
    if total == 0 or fp_status is None:
        return None

    fp_stmt = base_stmt.where(Alert.alert_resolution_status_id == fp_status)
    fp_count = db.session.execute(fp_stmt).scalar() or 0
    return (fp_count / total) * 100.0


def _escalation_rate(timeframe, filters: ComputedFilters) -> Optional[float]:
    escalated_status = db.session.execute(
        select(AlertStatus.status_id)
        .where(func.lower(AlertStatus.status_name) == 'escalated')
    ).scalar_one_or_none()

    base_stmt = select(func.count(Alert.alert_id))
    base_stmt = _apply_alert_filters(base_stmt, filters)
    base_stmt = _apply_timeframe(base_stmt, Alert.alert_creation_time, timeframe)
    base_stmt = _apply_access_filter_to_alert_query(base_stmt)
    total = db.session.execute(base_stmt).scalar() or 0
    if total == 0 or escalated_status is None:
        return None

    esc_stmt = base_stmt.where(Alert.alert_status_id == escalated_status)
    esc_count = db.session.execute(esc_stmt).scalar() or 0
    return (esc_count / total) * 100.0


def _alerts_window_count(timeframe, filters: ComputedFilters) -> Optional[float]:
    window = (filters.window or '24h').lower()
    if window == '2h':
        delta = timedelta(hours=2)
    elif window == '48h':
        delta = timedelta(hours=48)
    else:
        delta = timedelta(hours=24)
    now = datetime.utcnow()
    bounded = (now - delta, now)
    stmt = select(func.count(Alert.alert_id))
    stmt = _apply_alert_filters(stmt, filters)
    stmt = _apply_timeframe(stmt, Alert.alert_creation_time, bounded)
    stmt = _apply_access_filter_to_alert_query(stmt)
    return float(db.session.execute(stmt).scalar() or 0)


_NAMED_AGGREGATIONS: Dict[str, Callable[..., Optional[float]]] = {
    'mttd_seconds': _mttd_seconds,
    'mttr_seconds': _mttr_seconds,
    'false_positive_rate': _false_positive_rate,
    'escalation_rate': _escalation_rate,
    'alerts_window_count': _alerts_window_count,
}


def list_named_aggregations() -> List[Dict[str, str]]:
    return [
        {'name': 'mttd_seconds', 'label': 'Mean time to detect (seconds)', 'value_format': 'duration'},
        {'name': 'mttr_seconds', 'label': 'Mean time to resolve (seconds)', 'value_format': 'duration'},
        {'name': 'false_positive_rate', 'label': 'False positive rate', 'value_format': 'percentage'},
        {'name': 'escalation_rate', 'label': 'Escalation rate', 'value_format': 'percentage'},
        {'name': 'alerts_window_count', 'label': 'Alerts within window', 'value_format': 'number'},
    ]


def compute_named_aggregation(
    name: str,
    timeframe: Tuple[Optional[datetime], Optional[datetime]],
    filters: ComputedFilters,
) -> Optional[float]:
    fn = _NAMED_AGGREGATIONS.get(name)
    if fn is None:
        raise NamedAggregationError(f"Named aggregation '{name}' is not defined.")
    return fn(timeframe, filters)
