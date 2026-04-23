from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Set

from flask_login import current_user
from sqlalchemy import func, or_, select, cast, Integer, case, literal
from sqlalchemy.orm import Query, aliased

from app import db
from app.datamgmt.manage.manage_access_control_db import get_user_clients_id
from app.iris_engine.access_control.utils import ac_current_user_has_permission, ac_get_fast_user_cases_access
from app.models.alerts import Alert, AlertResolutionStatus, AlertStatus, Severity
from app.models.alerts import AlertCaseAssociation
from app.models.cases import Cases, CaseTags, CaseState, CasesEvent
from app.models.authorization import Permissions, User
from app.models.models import (
    CaseClassification,
    Client,
    Tags,
    CaseAssets,
    AssetsType,
    Ioc,
    IocType,
    IocLink,
    Notes,
    CaseTasks,
    ReviewStatus
)


class QueryExecutionError(Exception):
    """Raised when a widget cannot be executed due to an invalid configuration."""


@dataclass
class WidgetQueryResult:
    chart_type: str
    rows: List[Dict[str, Any]]
    group_labels: Sequence[str]
    value_labels: Sequence[str]
    select_labels: Sequence[str]


_MAX_TIME_BUCKET_POINTS = 2000


def _ensure_numeric(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    if isinstance(value, Decimal):
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    return None


def _format_number(value: Any) -> str:
    numeric = _ensure_numeric(value)
    if numeric is None:
        if value is None or value == '':
            return '--'
        return str(value)
    if numeric.is_integer():
        return f"{int(numeric):,}"
    return f"{numeric:,.2f}".rstrip('0').rstrip('.')


def _format_percentage(value: Optional[float]) -> str:
    if value is None:
        return '--'
    return f"{value:,.2f}%".rstrip('0').rstrip('.')


def _format_group_value(value: Any) -> str:
    if value is None or value == '':
        return 'N/A'
    return str(value)


def _format_time_group_value(value: Any, bucket: Optional[str]) -> str:
    if not isinstance(value, datetime):
        return _format_group_value(value)
    normalized_bucket = (bucket or '').lower()
    if normalized_bucket in {'minute', '5minute', '5m', '15minute', '15m', 'hour'}:
        return value.strftime('%Y-%m-%d %H:%M')
    if normalized_bucket == 'week':
        return value.strftime('Week %W %Y')
    if normalized_bucket == 'month':
        return value.strftime('%Y-%m')
    if normalized_bucket == 'year':
        return value.strftime('%Y')
    return value.strftime('%Y-%m-%d')


def _canonical_label_key(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or value == '':
        return 'N/A'
    return str(value)


def _compute_time_alias(time_column: Optional[str], time_bucket: Optional[str]) -> Optional[str]:
    if not isinstance(time_column, str) or '.' not in time_column:
        if isinstance(time_column, str):
            candidate = time_column.replace('.', '_').strip()
            return candidate or None
        return None
    table, column = time_column.split('.', 1)
    base = f"{table.strip()}_{column.strip()}"
    bucket = (time_bucket or '').strip().lower()
    return f"{base}_{bucket}" if bucket else base


def _floor_datetime_to_bucket(value: datetime, bucket: str) -> datetime:
    normalized = (bucket or '').lower()
    if normalized == 'minute':
        return value.replace(second=0, microsecond=0)
    if normalized in {'5minute', '5m'}:
        minute = value.minute - (value.minute % 5)
        return value.replace(minute=minute, second=0, microsecond=0)
    if normalized in {'15minute', '15m'}:
        minute = value.minute - (value.minute % 15)
        return value.replace(minute=minute, second=0, microsecond=0)
    if normalized == 'hour':
        return value.replace(minute=0, second=0, microsecond=0)
    if normalized == 'day':
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == 'week':
        start_of_week = value - timedelta(days=value.weekday())
        return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == 'month':
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if normalized == 'year':
        return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _advance_datetime_by_bucket(value: datetime, bucket: str) -> datetime:
    normalized = (bucket or '').lower()
    if normalized == 'minute':
        return value + timedelta(minutes=1)
    if normalized in {'5minute', '5m'}:
        return value + timedelta(minutes=5)
    if normalized in {'15minute', '15m'}:
        return value + timedelta(minutes=15)
    if normalized == 'hour':
        return value + timedelta(hours=1)
    if normalized == 'day':
        return value + timedelta(days=1)
    if normalized == 'week':
        return value + timedelta(weeks=1)
    if normalized == 'month':
        if value.month == 12:
            return value.replace(year=value.year + 1, month=1, day=1)
        return value.replace(month=value.month + 1, day=1)
    if normalized == 'year':
        return value.replace(year=value.year + 1, month=1, day=1)
    return value + timedelta(days=1)


def _generate_time_bucket_range(
    start: Optional[datetime],
    end: Optional[datetime],
    bucket: Optional[str],
    max_points: int = _MAX_TIME_BUCKET_POINTS
) -> List[datetime]:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return []
    normalized = (bucket or '').lower()
    if not normalized:
        return []

    if start > end:
        start, end = end, start

    current = _floor_datetime_to_bucket(start, normalized)
    end_floor = _floor_datetime_to_bucket(end, normalized)
    buckets: List[datetime] = []

    while current <= end_floor:
        buckets.append(current)
        if len(buckets) > max_points:
            return []
        next_value = _advance_datetime_by_bucket(current, normalized)
        if next_value <= current:
            break
        current = next_value

    return buckets


def _time_sort_key(value: Any) -> float:
    if isinstance(value, datetime):
        try:
            return float(value.timestamp())
        except (OverflowError, OSError):
            return float('-inf')
    return float('-inf')


def _normalize_display_mode(value: Optional[str]) -> str:
    if not value or not isinstance(value, str):
        return 'number'
    normalized = value.strip().lower()
    if normalized in {'percentage', 'percent'}:
        return 'percentage'
    if normalized in {'number_percentage', 'number-and-percentage', 'number and percentage', 'both'}:
        return 'number_percentage'
    return 'number'


CaseOwnerUser = aliased(User, name='case_owner_user')
CaseCreatorUser = aliased(User, name='case_creator_user')
CaseReviewerUser = aliased(User, name='case_reviewer_user')
AlertOwnerUser = aliased(User, name='alert_owner_user')
AlertAsset = aliased(CaseAssets, name='alert_asset')
CaseAsset = aliased(CaseAssets, name='case_asset')
AlertAssetType = aliased(AssetsType, name='alert_asset_type')
CaseAssetType = aliased(AssetsType, name='case_asset_type')
AlertIoc = aliased(Ioc, name='alert_ioc')
CaseIoc = aliased(Ioc, name='case_ioc')
AlertIocType = aliased(IocType, name='alert_ioc_type')
CaseIocType = aliased(IocType, name='case_ioc_type')
CaseIocLink = aliased(IocLink, name='case_ioc_link')
CaseEventAlias = aliased(CasesEvent, name='case_event')
CaseNoteAlias = aliased(Notes, name='case_note')
CaseTaskAlias = aliased(CaseTasks, name='case_task')


def _join_cases(query):
    return query.outerjoin(Cases, Alert.cases)


def _join_case_owner(query):
    return query.outerjoin(CaseOwnerUser, Cases.owner)


def _join_case_creator(query):
    return query.outerjoin(CaseCreatorUser, Cases.user)


def _join_case_reviewer(query):
    return query.outerjoin(CaseReviewerUser, Cases.reviewer)


def _join_alert_owner(query):
    return query.outerjoin(AlertOwnerUser, Alert.owner)


def _join_case_tags_table(query):
    return query.outerjoin(CaseTags, CaseTags.case_id == Cases.case_id)


def _join_tags_table(query):
    # Case tags join is registered before reaching this point, so reuse its alias when linking tags.
    return query.outerjoin(Tags, Tags.id == CaseTags.tag_id)


def _join_case_state(query):
    return query.outerjoin(CaseState, CaseState.state_id == Cases.state_id)


def _join_alert_assets(query):
    return query.outerjoin(AlertAsset, Alert.assets)


def _join_case_assets(query):
    return query.outerjoin(CaseAsset, CaseAsset.case_id == Cases.case_id)


def _join_alert_asset_types(query):
    return query.outerjoin(AlertAssetType, AlertAsset.asset_type)


def _join_case_asset_types(query):
    return query.outerjoin(CaseAssetType, CaseAsset.asset_type)


def _join_alert_iocs(query):
    return query.outerjoin(AlertIoc, Alert.iocs)


def _join_case_iocs(query):
    query = query.outerjoin(CaseIocLink, CaseIocLink.case_id == Cases.case_id)
    return query.outerjoin(CaseIoc, CaseIoc.ioc_id == CaseIocLink.ioc_id)


def _join_alert_ioc_types(query):
    return query.outerjoin(AlertIocType, AlertIoc.ioc_type)


def _join_case_ioc_types(query):
    return query.outerjoin(CaseIocType, CaseIoc.ioc_type)


def _join_case_events(query):
    return query.outerjoin(CaseEventAlias, CaseEventAlias.case_id == Cases.case_id)


def _join_case_notes(query):
    return query.outerjoin(CaseNoteAlias, CaseNoteAlias.note_case_id == Cases.case_id)


def _join_case_tasks(query):
    return query.outerjoin(CaseTaskAlias, CaseTaskAlias.task_case_id == Cases.case_id)


_AGGREGATIONS = {
    'count': lambda column: func.count(column),
    'sum': lambda column: func.sum(column),
    'avg': lambda column: func.avg(column),
    'min': lambda column: func.min(column),
    'max': lambda column: func.max(column)
}

_OPERATORS = {
    'eq': lambda column, value: column == value,
    'neq': lambda column, value: column != value,
    'gt': lambda column, value: column > value,
    'gte': lambda column, value: column >= value,
    'lt': lambda column, value: column < value,
    'lte': lambda column, value: column <= value,
    'in': lambda column, value: column.in_(value if isinstance(value, (list, tuple, set)) else [value]),
    'nin': lambda column, value: ~column.in_(value if isinstance(value, (list, tuple, set)) else [value]),
    'between': lambda column, value: column.between(value[0], value[1]) if isinstance(value, (list, tuple)) and len(value) == 2 else None,
    'contains': lambda column, value: column.ilike(f"%{value}%")
}


def _capitalize_label(label: str) -> str:
    if not label:
        return label
    return label.replace('_', ' ').strip().capitalize()


class _WidgetQueryBuilder:
    def __init__(self):
        self.selects: List[Any] = []
        self.select_labels: List[str] = []
        self.group_by_exprs: List[Any] = []
        self.group_labels: List[str] = []
        self.aggregated_labels: List[str] = []
        self.aggregated_exprs: Dict[str, Any] = {}
        self.filters: List[Any] = []
        self.joins: List[str] = []
        self.chart_type: str = ''

    def add_join(self, table_name: str):
        if table_name not in self.joins:
            self.joins.append(table_name)

    def add_group_by(self, expr: Any, label: str):
        if expr not in self.group_by_exprs:
            self.group_by_exprs.append(expr)
        if label not in self.group_labels:
            self.group_labels.append(label)

    def add_select(self, expr: Any, label: str, aggregated: bool):
        labeled_expr = expr.label(label)
        self.selects.append(labeled_expr)
        self.select_labels.append(label)
        if aggregated:
            self.aggregated_labels.append(label)
            self.aggregated_exprs[label] = labeled_expr
        else:
            self.add_group_by(expr, label)


def _between_dates(column, start: Optional[datetime], end: Optional[datetime]):
    expressions = []
    if start is not None:
        expressions.append(column >= start)
    if end is not None:
        expressions.append(column <= end)
    return expressions


class WidgetQueryExecutor:
    """Builds and executes SQLAlchemy queries for dashboard widgets."""

    _BASE_TABLE = 'alerts'

    _TABLES: Dict[str, Dict[str, Any]] = {
        'alerts': {
            'model': Alert,
            'columns': {
                'alert_id': Alert.alert_id,
                'alert_uuid': Alert.alert_uuid,
                'alert_title': Alert.alert_title,
                'alert_source': Alert.alert_source,
                'alert_source_ref': Alert.alert_source_ref,
                'alert_description': Alert.alert_description,
                'alert_creation_time': Alert.alert_creation_time,
                'alert_source_event_time': Alert.alert_source_event_time,
                'alert_customer_id': Alert.alert_customer_id,
                'alert_resolution_status_id': Alert.alert_resolution_status_id,
                'alert_status_id': Alert.alert_status_id,
                'alert_severity_id': Alert.alert_severity_id,
                'alert_owner_id': Alert.alert_owner_id,
                'alert_classification_id': Alert.alert_classification_id,
                'alert_tags': Alert.alert_tags
            },
            'default_time_column': Alert.alert_creation_time
        },
        'client': {
            'model': Client,
            'columns': {
                'client_id': Client.client_id,
                'name': Client.name
            },
            'join': lambda query: query.outerjoin(Client, Alert.customer)
        },
        'alert_resolution_status': {
            'model': AlertResolutionStatus,
            'columns': {
                'resolution_status_id': AlertResolutionStatus.resolution_status_id,
                'resolution_status_name': AlertResolutionStatus.resolution_status_name
            },
            'join': lambda query: query.outerjoin(AlertResolutionStatus, Alert.resolution_status)
        },
        'alert_status': {
            'model': AlertStatus,
            'columns': {
                'status_id': AlertStatus.status_id,
                'status_name': AlertStatus.status_name
            },
            'join': lambda query: query.outerjoin(AlertStatus, Alert.status)
        },
        'severities': {
            'model': Severity,
            'columns': {
                'severity_id': Severity.severity_id,
                'severity_name': Severity.severity_name
            },
            'join': lambda query: query.outerjoin(Severity, Alert.severity)
        },
        'case_classification': {
            'model': CaseClassification,
            'columns': {
                'id': CaseClassification.id,
                'name': CaseClassification.name,
                'name_expanded': CaseClassification.name_expanded
            },
            'join': lambda query: query.outerjoin(CaseClassification, Alert.classification)
        },
        'cases': {
            'model': Cases,
            'columns': {
                'case_id': Cases.case_id,
                'name': Cases.name,
                'owner_id': Cases.owner_id,
                'creator_id': Cases.user_id,
                'reviewer_id': Cases.reviewer_id,
                'review_status_id': Cases.review_status_id,
                'state_id': Cases.state_id,
                'status_id': Cases.status_id,
                'severity_id': Cases.severity_id,
                'classification_id': Cases.classification_id,
                'client_id': Cases.client_id,
                'open_date': Cases.open_date,
                'close_date': Cases.close_date,
                'initial_date': Cases.initial_date
            },
            'join': _join_cases
        },
        'case_state': {
            'model': CaseState,
            'columns': {
                'state_id': CaseState.state_id,
                'state_name': CaseState.state_name,
                'state_description': CaseState.state_description
            },
            'join': _join_case_state
        },
        'case_tags': {
            'model': CaseTags,
            'columns': {
                'case_id': CaseTags.case_id,
                'tag_id': CaseTags.tag_id
            },
            'join': _join_case_tags_table
        },
        'alert_owner': {
            'model': User,
            'columns': {
                'id': AlertOwnerUser.id,
                'username': AlertOwnerUser.user,
                'name': AlertOwnerUser.name
            },
            'join': _join_alert_owner
        },
        'case_owner': {
            'model': User,
            'columns': {
                'id': CaseOwnerUser.id,
                'username': CaseOwnerUser.user,
                'name': CaseOwnerUser.name
            },
            'join': _join_case_owner
        },
        'case_creator': {
            'model': User,
            'columns': {
                'id': CaseCreatorUser.id,
                'username': CaseCreatorUser.user,
                'name': CaseCreatorUser.name
            },
            'join': _join_case_creator
        },
        'case_reviewer': {
            'model': User,
            'columns': {
                'id': CaseReviewerUser.id,
                'username': CaseReviewerUser.user,
                'name': CaseReviewerUser.name
            },
            'join': _join_case_reviewer
        },
        'tags': {
            'model': Tags,
            'columns': {
                'id': Tags.id,
                'tag_title': Tags.tag_title,
                'tag_namespace': Tags.tag_namespace,
                'tag_creation_date': Tags.tag_creation_date
            },
            'join': _join_tags_table
        },
        'alert_assets': {
            'model': AlertAsset,
            'columns': {
                'asset_id': AlertAsset.asset_id,
                'asset_uuid': AlertAsset.asset_uuid,
                'asset_name': AlertAsset.asset_name,
                'asset_description': AlertAsset.asset_description,
                'asset_domain': AlertAsset.asset_domain,
                'asset_ip': AlertAsset.asset_ip,
                'asset_info': AlertAsset.asset_info,
                'asset_compromise_status_id': AlertAsset.asset_compromise_status_id,
                'asset_type_id': AlertAsset.asset_type_id,
                'asset_tags': AlertAsset.asset_tags,
                'case_id': AlertAsset.case_id,
                'date_added': AlertAsset.date_added,
                'date_update': AlertAsset.date_update,
                'user_id': AlertAsset.user_id
            },
            'join': _join_alert_assets
        },
        'alert_asset_types': {
            'model': AlertAssetType,
            'columns': {
                'asset_id': AlertAssetType.asset_id,
                'asset_name': AlertAssetType.asset_name,
                'asset_description': AlertAssetType.asset_description,
                'asset_icon_not_compromised': AlertAssetType.asset_icon_not_compromised,
                'asset_icon_compromised': AlertAssetType.asset_icon_compromised
            },
            'join': _join_alert_asset_types
        },
        'alert_iocs': {
            'model': AlertIoc,
            'columns': {
                'ioc_id': AlertIoc.ioc_id,
                'ioc_uuid': AlertIoc.ioc_uuid,
                'ioc_value': AlertIoc.ioc_value,
                'ioc_type_id': AlertIoc.ioc_type_id,
                'ioc_description': AlertIoc.ioc_description,
                'ioc_tags': AlertIoc.ioc_tags,
                'user_id': AlertIoc.user_id,
                'ioc_misp': AlertIoc.ioc_misp,
                'ioc_tlp_id': AlertIoc.ioc_tlp_id
            },
            'join': _join_alert_iocs
        },
        'alert_ioc_types': {
            'model': AlertIocType,
            'columns': {
                'type_id': AlertIocType.type_id,
                'type_name': AlertIocType.type_name,
                'type_description': AlertIocType.type_description,
                'type_taxonomy': AlertIocType.type_taxonomy,
                'type_validation_regex': AlertIocType.type_validation_regex,
                'type_validation_expect': AlertIocType.type_validation_expect
            },
            'join': _join_alert_ioc_types
        },
        'case_assets': {
            'model': CaseAsset,
            'columns': {
                'asset_id': CaseAsset.asset_id,
                'asset_uuid': CaseAsset.asset_uuid,
                'asset_name': CaseAsset.asset_name,
                'asset_description': CaseAsset.asset_description,
                'asset_domain': CaseAsset.asset_domain,
                'asset_ip': CaseAsset.asset_ip,
                'asset_info': CaseAsset.asset_info,
                'asset_compromise_status_id': CaseAsset.asset_compromise_status_id,
                'asset_type_id': CaseAsset.asset_type_id,
                'asset_tags': CaseAsset.asset_tags,
                'case_id': CaseAsset.case_id,
                'date_added': CaseAsset.date_added,
                'date_update': CaseAsset.date_update,
                'user_id': CaseAsset.user_id
            },
            'join': _join_case_assets
        },
        'case_asset_types': {
            'model': CaseAssetType,
            'columns': {
                'asset_id': CaseAssetType.asset_id,
                'asset_name': CaseAssetType.asset_name,
                'asset_description': CaseAssetType.asset_description,
                'asset_icon_not_compromised': CaseAssetType.asset_icon_not_compromised,
                'asset_icon_compromised': CaseAssetType.asset_icon_compromised
            },
            'join': _join_case_asset_types
        },
        'case_iocs': {
            'model': CaseIoc,
            'columns': {
                'ioc_id': CaseIoc.ioc_id,
                'ioc_uuid': CaseIoc.ioc_uuid,
                'ioc_value': CaseIoc.ioc_value,
                'ioc_type_id': CaseIoc.ioc_type_id,
                'ioc_description': CaseIoc.ioc_description,
                'ioc_tags': CaseIoc.ioc_tags,
                'user_id': CaseIoc.user_id,
                'ioc_misp': CaseIoc.ioc_misp,
                'ioc_tlp_id': CaseIoc.ioc_tlp_id
            },
            'join': _join_case_iocs
        },
        'case_ioc_types': {
            'model': CaseIocType,
            'columns': {
                'type_id': CaseIocType.type_id,
                'type_name': CaseIocType.type_name,
                'type_description': CaseIocType.type_description,
                'type_taxonomy': CaseIocType.type_taxonomy,
                'type_validation_regex': CaseIocType.type_validation_regex,
                'type_validation_expect': CaseIocType.type_validation_expect
            },
            'join': _join_case_ioc_types
        },
        'case_events': {
            'model': CaseEventAlias,
            'columns': {
                'event_id': CaseEventAlias.event_id,
                'parent_event_id': CaseEventAlias.parent_event_id,
                'case_id': CaseEventAlias.case_id,
                'event_title': CaseEventAlias.event_title,
                'event_source': CaseEventAlias.event_source,
                'event_content': CaseEventAlias.event_content,
                'event_raw': CaseEventAlias.event_raw,
                'event_date': CaseEventAlias.event_date,
                'event_added': CaseEventAlias.event_added,
                'event_in_graph': CaseEventAlias.event_in_graph,
                'event_in_summary': CaseEventAlias.event_in_summary,
                'user_id': CaseEventAlias.user_id,
                'event_color': CaseEventAlias.event_color,
                'event_tags': CaseEventAlias.event_tags,
                'event_tz': CaseEventAlias.event_tz,
                'event_date_wtz': CaseEventAlias.event_date_wtz,
                'event_is_flagged': CaseEventAlias.event_is_flagged
            },
            'join': _join_case_events
        },
        'case_notes': {
            'model': CaseNoteAlias,
            'columns': {
                'note_id': CaseNoteAlias.note_id,
                'note_uuid': CaseNoteAlias.note_uuid,
                'note_title': CaseNoteAlias.note_title,
                'note_content': CaseNoteAlias.note_content,
                'note_user': CaseNoteAlias.note_user,
                'note_creationdate': CaseNoteAlias.note_creationdate,
                'note_lastupdate': CaseNoteAlias.note_lastupdate,
                'note_case_id': CaseNoteAlias.note_case_id,
                'directory_id': CaseNoteAlias.directory_id
            },
            'join': _join_case_notes
        },
        'case_tasks': {
            'model': CaseTaskAlias,
            'columns': {
                'id': CaseTaskAlias.id,
                'task_uuid': CaseTaskAlias.task_uuid,
                'task_title': CaseTaskAlias.task_title,
                'task_description': CaseTaskAlias.task_description,
                'task_tags': CaseTaskAlias.task_tags,
                'task_open_date': CaseTaskAlias.task_open_date,
                'task_close_date': CaseTaskAlias.task_close_date,
                'task_last_update': CaseTaskAlias.task_last_update,
                'task_userid_open': CaseTaskAlias.task_userid_open,
                'task_userid_close': CaseTaskAlias.task_userid_close,
                'task_userid_update': CaseTaskAlias.task_userid_update,
                'task_status_id': CaseTaskAlias.task_status_id,
                'task_case_id': CaseTaskAlias.task_case_id
            },
            'join': _join_case_tasks
        },
        'review_status': {
            'model': ReviewStatus,
            'columns': {
                'id': ReviewStatus.id,
                'status_name': ReviewStatus.status_name
            },
            'join': lambda query: query.outerjoin(ReviewStatus, Cases.review_status)
        }
    }

    def __init__(self, definition: Dict[str, Any]):
        self.definition = definition or {}
        self.builder = _WidgetQueryBuilder()
        options = self.definition.get('options') or {}
        self.time_column_spec = options.get('time_column') or 'alerts.alert_creation_time'
        self._normalized_time_column_spec = self._normalize_table_column_value(self.time_column_spec)
        raw_time_bucket = self.definition.get('time_bucket')
        self.time_bucket = raw_time_bucket.strip().lower() if isinstance(raw_time_bucket, str) else ''
        self._time_bucket_label = ''
        self._projection_tables: Set[str] = self._collect_projection_tables()

    def execute(self, timeframe: Tuple[Optional[datetime], Optional[datetime]]) -> WidgetQueryResult:
        widgets_fields = self.definition.get('fields') or []
        if not widgets_fields:
            raise QueryExecutionError('The widget must define at least one field.')

        self.builder.chart_type = (self.definition.get('chart_type') or '').lower()
        if not self.builder.chart_type:
            raise QueryExecutionError('Missing chart type in widget definition.')

        for field in widgets_fields:
            self._add_field(field)

        for group_entry in self.definition.get('group_by', []) or []:
            self._apply_group_by(group_entry)

        self._ensure_time_bucket_group()

        for filter_entry in self.definition.get('filters', []) or []:
            self._apply_filter(filter_entry)

        start, end = timeframe
        self._apply_timeframe(start, end)
        self._apply_access_filters()

        query = self._build_query()
        query = self._apply_sorting(query)
        query = self._apply_limit(query)

        rows = query.all()
        mapped_rows = [dict(row._mapping) for row in rows]

        return WidgetQueryResult(
            chart_type=self.builder.chart_type,
            rows=mapped_rows,
            group_labels=self.builder.group_labels,
            value_labels=self.builder.aggregated_labels or [label for label in self.builder.select_labels if label in self.builder.group_labels],
            select_labels=self.builder.select_labels
        )

    def _get_table(self, table_name: str) -> Dict[str, Any]:
        table = self._TABLES.get(table_name)
        if not table:
            raise QueryExecutionError(f"Table '{table_name}' is not allowed in custom dashboards.")
        return table

    def _get_column(self, table_name: str, column_name: str):
        table = self._get_table(table_name)
        columns = table.get('columns', {})
        column = columns.get(column_name)
        if column is None:
            raise QueryExecutionError(f"Column '{column_name}' is not allowed for table '{table_name}'.")
        if table_name in {'case_owner', 'case_creator', 'case_reviewer', 'case_tags', 'tags', 'case_assets', 'case_asset_types', 'case_iocs', 'case_ioc_types', 'case_events', 'case_notes', 'case_tasks', 'review_status', 'case_state'}:
            self.builder.add_join('cases')
        if table_name == 'tags':
            self.builder.add_join('case_tags')
        if table_name == 'case_asset_types':
            self.builder.add_join('case_assets')
        if table_name == 'case_ioc_types':
            self.builder.add_join('case_iocs')
        if table_name == 'alert_asset_types':
            self.builder.add_join('alert_assets')
        if table_name == 'alert_ioc_types':
            self.builder.add_join('alert_iocs')
        if table_name != self._BASE_TABLE:
            self.builder.add_join(table_name)
        return column

    def _add_field(self, field_definition: Dict[str, Any]):
        table_name = field_definition.get('table')
        column_name = field_definition.get('column')
        if not table_name or not column_name:
            raise QueryExecutionError('Each field must specify a table and column.')

        column = self._get_column(table_name, column_name)
        alias = field_definition.get('alias') or f"{table_name}_{column_name}"
        aggregation = (field_definition.get('aggregation') or '').lower() or None
        field_filter_definition = field_definition.get('filter')

        if aggregation:
            filter_expression = None
            if field_filter_definition:
                filter_expression = self._build_filter_expression(field_filter_definition)
            expr = self._build_aggregate_expression(aggregation, column, filter_expression)
            self.builder.add_select(expr, alias, aggregated=True)
        else:
            if field_filter_definition:
                raise QueryExecutionError('Non-aggregated fields cannot specify a filter.')
            self.builder.add_select(column, alias, aggregated=False)

    def _apply_group_by(self, group_entry: str):
        table_name, column_name = self._parse_table_column(group_entry)
        column = self._get_column(table_name, column_name)
        alias = f"{table_name}_{column_name}"
        is_time_group = self._is_time_column(group_entry)

        if is_time_group and self.time_bucket:
            truncated_column = self._apply_time_bucket(column)
            alias = self._resolve_time_bucket_label(table_name, column_name)
            self.builder.add_select(truncated_column, alias, aggregated=False)
            self._time_bucket_label = alias
            self._promote_time_group()
        else:
            self.builder.add_select(column, alias, aggregated=False)

    def _apply_filter(self, filter_definition: Dict[str, Any]):
        table_name = (filter_definition or {}).get('table')
        if table_name in {'tags', 'case_tags'} and table_name not in self._projection_tables:
            expression = self._build_case_scoped_tag_filter(filter_definition)
        else:
            expression = self._build_filter_expression(filter_definition)
        self.builder.filters.append(expression)

    def _collect_projection_tables(self) -> Set[str]:
        tables: Set[str] = set()
        for field in self.definition.get('fields') or []:
            if isinstance(field, dict) and field.get('table'):
                tables.add(field['table'])
        for group_entry in self.definition.get('group_by') or []:
            if isinstance(group_entry, str) and '.' in group_entry:
                tables.add(group_entry.split('.', 1)[0].strip())
        return tables

    def _build_case_scoped_tag_filter(self, filter_definition: Dict[str, Any]):
        # Many-to-many joins on tags inflate counts; route tag-only filters through
        # a Cases.case_id IN (subquery) so the main query stays flat.
        if not isinstance(filter_definition, dict):
            raise QueryExecutionError('Invalid filter definition supplied.')

        table_name = filter_definition.get('table')
        column_name = filter_definition.get('column')
        operator = (filter_definition.get('operator') or '').lower()
        value = filter_definition.get('value')

        if not table_name or not column_name or not operator:
            raise QueryExecutionError('Filters must define table, column, and operator.')

        table = self._get_table(table_name)
        column = table.get('columns', {}).get(column_name)
        if column is None:
            raise QueryExecutionError(f"Column '{column_name}' is not allowed for table '{table_name}'.")

        operator_fn = _OPERATORS.get(operator)
        if operator_fn is None:
            raise QueryExecutionError(f"Operator '{operator}' is not supported.")

        condition = operator_fn(column, value)
        if condition is None:
            raise QueryExecutionError(f"Operator '{operator}' expects a different value format.")

        if table_name == 'tags':
            subquery = (
                select(CaseTags.case_id)
                .join(Tags, Tags.id == CaseTags.tag_id)
                .where(condition)
            )
        else:
            subquery = select(CaseTags.case_id).where(condition)

        self.builder.add_join('cases')
        return Cases.case_id.in_(subquery)

    def _apply_timeframe(self, start: Optional[datetime], end: Optional[datetime]):
        table_name, column_name = self._parse_table_column(self.time_column_spec)
        column = self._get_column(table_name, column_name)

        for expression in _between_dates(column, start, end):
            self.builder.filters.append(expression)

    def _ensure_time_bucket_group(self):
        if not self.time_bucket:
            return

        if self._time_bucket_label and self._time_bucket_label in self.builder.select_labels:
            return

        table_name, column_name = self._parse_table_column(self.time_column_spec)
        column = self._get_column(table_name, column_name)
        alias = self._resolve_time_bucket_label(table_name, column_name)
        truncated_column = self._apply_time_bucket(column)
        self.builder.add_select(truncated_column, alias, aggregated=False)
        self._time_bucket_label = alias
        self._promote_time_group()

    def _apply_access_filters(self):
        if ac_current_user_has_permission(Permissions.server_administrator):
            return

        user_id = getattr(current_user, 'id', None)
        if not user_id:
            # Without a logged-in user we cannot determine scope; deny by default.
            self.builder.filters.append(Alert.alert_id == -1)
            return

        client_ids = get_user_clients_id(user_id) or []
        case_ids = ac_get_fast_user_cases_access(user_id) or []

        access_conditions = []

        if client_ids:
            access_conditions.append(Alert.alert_customer_id.in_(client_ids))

        if case_ids:
            case_alerts_subquery = select(AlertCaseAssociation.alert_id).where(
                AlertCaseAssociation.case_id.in_(case_ids)
            )
            access_conditions.append(Alert.alert_id.in_(case_alerts_subquery))

        if not access_conditions:
            # User has no accessible scope -> no data should be returned.
            self.builder.filters.append(Alert.alert_id == -1)
            return

        if len(access_conditions) == 1:
            self.builder.filters.append(access_conditions[0])
        else:
            self.builder.filters.append(or_(*access_conditions))

    def _build_query(self) -> Query:
        if not any(label in self.builder.select_labels for label in self.builder.aggregated_labels):
            if not self.builder.group_labels:
                raise QueryExecutionError('Widgets must contain at least one aggregated field or grouping column.')

        query = db.session.query(*self.builder.selects)
        query = query.select_from(Alert)
        for join_table in self.builder.joins:
            table = self._get_table(join_table)
            join_callable = table.get('join')
            if join_callable is None:
                raise QueryExecutionError(f"No join strategy registered for table '{join_table}'.")
            query = join_callable(query)

        if self.builder.filters:
            query = query.filter(*self.builder.filters)

        if self.builder.group_by_exprs:
            query = query.group_by(*self.builder.group_by_exprs)

        return query

    def _apply_sorting(self, query: Query) -> Query:
        options = self.definition.get('options') or {}
        sort_direction = (options.get('sort') or '').lower()
        if not sort_direction:
            if self._time_bucket_label:
                try:
                    time_index = self.builder.group_labels.index(self._time_bucket_label)
                    time_expression = self.builder.group_by_exprs[time_index]
                except (ValueError, IndexError):
                    time_expression = None
                    time_index = -1
                if time_expression is not None:
                    order_clauses = [time_expression.asc()]
                    for idx, expr in enumerate(self.builder.group_by_exprs):
                        if idx == time_index:
                            continue
                        order_clauses.append(expr.asc())
                    return query.order_by(*order_clauses)
            return query

        order_expression = None
        if self.builder.aggregated_labels:
            primary_label = self.builder.aggregated_labels[0]
            order_expression = self.builder.aggregated_exprs.get(primary_label)
        elif self.builder.group_by_exprs:
            order_expression = self.builder.group_by_exprs[0]

        if order_expression is None:
            return query

        if sort_direction == 'desc':
            return query.order_by(order_expression.desc())
        if sort_direction == 'asc':
            return query.order_by(order_expression.asc())
        return query

    def _apply_limit(self, query: Query) -> Query:
        options = self.definition.get('options') or {}
        limit_value = options.get('limit')
        if isinstance(limit_value, int) and limit_value > 0:
            return query.limit(limit_value)
        return query

    def _parse_table_column(self, value: str) -> Tuple[str, str]:
        if not value or '.' not in value:
            raise QueryExecutionError('Expected table.column format in widget definition.')
        table_name, column_name = value.split('.', 1)
        return table_name.strip(), column_name.strip()

    def _build_filter_expression(self, filter_definition: Dict[str, Any]):
        if not isinstance(filter_definition, dict):
            raise QueryExecutionError('Invalid filter definition supplied.')

        table_name = filter_definition.get('table')
        column_name = filter_definition.get('column')
        operator = (filter_definition.get('operator') or '').lower()
        value = filter_definition.get('value')

        if not table_name or not column_name or not operator:
            raise QueryExecutionError('Filters must define table, column, and operator.')

        column = self._get_column(table_name, column_name)
        operator_fn = _OPERATORS.get(operator)
        if operator_fn is None:
            raise QueryExecutionError(f"Operator '{operator}' is not supported.")

        expression = operator_fn(column, value)
        if expression is None:
            raise QueryExecutionError(f"Operator '{operator}' expects a different value format.")

        return expression

    def _build_aggregate_expression(self, aggregation: str, column, filter_expression):
        normalized = aggregation.lower()

        if filter_expression is not None:
            if normalized == 'count':
                return func.coalesce(func.sum(case((filter_expression, 1), else_=0)), 0)
            if normalized == 'sum':
                return func.coalesce(func.sum(case((filter_expression, column), else_=0)), 0)
            if normalized == 'avg':
                return func.avg(case((filter_expression, column), else_=None))
            if normalized == 'min':
                return func.min(case((filter_expression, column), else_=None))
            if normalized == 'max':
                return func.max(case((filter_expression, column), else_=None))
            if normalized == 'ratio':
                base_column = column or Alert.alert_id
                numerator = func.sum(case((filter_expression, 1), else_=0))
                denominator = func.nullif(func.count(base_column), 0)
                ratio_expr = (numerator * literal(100.0)) / denominator
                return func.coalesce(ratio_expr, 0)
            raise QueryExecutionError(f"Aggregation '{aggregation}' with filter is not supported.")

        if normalized == 'ratio':
            raise QueryExecutionError("Ratio aggregation requires a filter to be specified.")

        agg_fn = _AGGREGATIONS.get(normalized)
        if agg_fn is None:
            raise QueryExecutionError(f"Aggregation '{aggregation}' is not supported.")
        return agg_fn(column)

    def _promote_time_group(self):
        if not self._time_bucket_label:
            return
        try:
            label_index = self.builder.group_labels.index(self._time_bucket_label)
        except ValueError:
            return
        if label_index == 0:
            return
        if label_index < len(self.builder.group_labels):
            self.builder.group_labels.insert(0, self.builder.group_labels.pop(label_index))
        if label_index < len(self.builder.group_by_exprs):
            self.builder.group_by_exprs.insert(0, self.builder.group_by_exprs.pop(label_index))

    def _normalize_table_column_value(self, value: Optional[str]) -> str:
        if not isinstance(value, str):
            return ''
        return value.replace(' ', '').lower()

    def _is_time_column(self, group_entry: str) -> bool:
        return self._normalize_table_column_value(group_entry) == self._normalized_time_column_spec

    def _resolve_time_bucket_label(self, table_name: str, column_name: str) -> str:
        if not self.time_bucket:
            return f"{table_name}_{column_name}"
        return f"{table_name}_{column_name}_{self.time_bucket}"

    def _apply_time_bucket(self, column):
        if not self.time_bucket:
            return column

        bucket = self.time_bucket
        if bucket in {'minute', 'hour', 'day', 'week', 'month', 'year'}:
            return func.date_trunc(bucket, column)

        if bucket in {'5minute', '5m'}:
            minute_part = cast(func.date_part('minute', column), Integer)
            remainder = cast(minute_part % 5, Integer)
            return func.date_trunc('minute', column) - func.make_interval(0, 0, 0, 0, 0, remainder)

        if bucket in {'15minute', '15m'}:
            minute_part = cast(func.date_part('minute', column), Integer)
            remainder = cast(minute_part % 15, Integer)
            return func.date_trunc('minute', column) - func.make_interval(0, 0, 0, 0, 0, remainder)

        return func.date_trunc(bucket, column)


def execute_widget(definition: Dict[str, Any], timeframe: Tuple[Optional[datetime], Optional[datetime]]) -> WidgetQueryResult:
    executor = WidgetQueryExecutor(definition)
    return executor.execute(timeframe)


def format_widget_payload(
    result: WidgetQueryResult,
    definition: Optional[Dict[str, Any]] = None,
    timeframe: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None
) -> Dict[str, Any]:
    definition = definition or {}
    options = definition.get('options') or {}
    display_mode = _normalize_display_mode(options.get('display') or options.get('display_mode'))
    chart_type_raw = (result.chart_type or '').lower()
    chart_type = 'line' if chart_type_raw == 'timechart' else chart_type_raw
    time_bucket = (definition.get('time_bucket') or '').strip().lower()
    time_column_spec = options.get('time_column') or 'alerts.alert_creation_time'
    expected_time_alias = _compute_time_alias(time_column_spec, time_bucket)

    timeframe_start: Optional[datetime] = None
    timeframe_end: Optional[datetime] = None
    if isinstance(timeframe, tuple) and len(timeframe) == 2:
        timeframe_start, timeframe_end = timeframe

    if chart_type in {'bar', 'line', 'pie'}:
        group_labels = list(result.group_labels)
        value_labels = list(result.value_labels)

        effective_group_labels = group_labels[:]
        time_axis_enabled = False
        if expected_time_alias and expected_time_alias in effective_group_labels:
            time_axis_enabled = True
            effective_group_labels = [expected_time_alias] + [label for label in effective_group_labels if label != expected_time_alias]

        primary_group_label = effective_group_labels[0] if effective_group_labels else None
        secondary_group_labels = effective_group_labels[1:] if len(effective_group_labels) > 1 else []

        label_entries: List[Dict[str, Any]] = []
        label_index: Dict[str, int] = {}

        def remember_label(raw_value: Any) -> str:
            key = _canonical_label_key(raw_value)
            display_value = _format_time_group_value(raw_value, time_bucket) if time_axis_enabled else _format_group_value(raw_value)
            if key not in label_index:
                label_index[key] = len(label_entries)
                label_entries.append({'key': key, 'raw': raw_value, 'display': display_value})
            return key

        axis_metadata: Optional[Dict[str, Any]] = None

        if (
            time_axis_enabled
            and time_bucket
            and timeframe_start is not None
            and timeframe_end is not None
        ):
            prefilled_buckets = _generate_time_bucket_range(timeframe_start, timeframe_end, time_bucket)
            for bucket_value in prefilled_buckets:
                remember_label(bucket_value)

        if chart_type != 'pie' and len(effective_group_labels) > 1 and primary_group_label is not None:
            dataset_map: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]] = {}
            totals: Dict[str, Optional[float]] = {label: 0.0 for label in value_labels}
            counts: Dict[str, int] = {label: 0 for label in value_labels}

            for row in result.rows:
                primary_raw = row.get(primary_group_label)
                label_key = remember_label(primary_raw)
                series_values = tuple(
                    _format_group_value(row.get(series_label))
                    for series_label in secondary_group_labels
                )

                for value_label in value_labels:
                    dataset_key = (value_label, series_values)
                    entry = dataset_map.setdefault(dataset_key, {
                        'value_label': value_label,
                        'series_values': series_values,
                        'data': {},
                        'has_values': False
                    })

                    value = row.get(value_label)
                    numeric_value = _ensure_numeric(value)
                    if numeric_value is not None:
                        entry['has_values'] = True
                        entry['data'][label_key] = numeric_value
                        totals[value_label] = (totals.get(value_label) or 0.0) + numeric_value
                        counts[value_label] = counts.get(value_label, 0) + 1
                    else:
                        entry['data'].setdefault(label_key, 0)

            if not dataset_map:
                for value_label in value_labels:
                    dataset_map[(value_label, tuple())] = {
                        'value_label': value_label,
                        'series_values': tuple(),
                        'data': {},
                        'has_values': False
                    }

            for value_label, count in counts.items():
                if count == 0:
                    totals[value_label] = None

            if time_axis_enabled:
                label_entries.sort(key=lambda item: (_time_sort_key(item['raw']), item['display']))
                axis_metadata = {
                    'type': 'time',
                    'bucket': time_bucket,
                    'display_labels': [entry['display'] for entry in label_entries]
                }
                if timeframe_start is not None and timeframe_end is not None:
                    range_start = timeframe_start
                    range_end = timeframe_end
                    if time_bucket:
                        range_start = _floor_datetime_to_bucket(timeframe_start, time_bucket)
                        end_floor = _floor_datetime_to_bucket(timeframe_end, time_bucket)
                        next_end = _advance_datetime_by_bucket(end_floor, time_bucket)
                        range_end = next_end if next_end > end_floor else end_floor
                    axis_metadata['range'] = {
                        'start': range_start.isoformat(),
                        'end': range_end.isoformat()
                    }

            label_order_keys = [entry['key'] for entry in label_entries]
            display_labels = [entry['display'] for entry in label_entries]
            chart_labels = label_order_keys if time_axis_enabled else display_labels

            formatted_datasets: List[Dict[str, Any]] = []
            for dataset_key, entry in dataset_map.items():
                data_points = [entry['data'].get(label_key, 0) for label_key in label_order_keys]
                dataset_total = sum(entry['data'].values()) if entry.get('has_values') else None
                series_components = [component for component in entry['series_values'] if component]
                base_label = _capitalize_label(entry['value_label'])
                if series_components:
                    dataset_label = f"{base_label} – {' / '.join(series_components)}"
                else:
                    dataset_label = base_label
                series_key_str = '::'.join(entry['series_values'])
                value_key = entry['value_label'] if not series_key_str else f"{entry['value_label']}::{series_key_str}"
                formatted_datasets.append({
                    'label': dataset_label,
                    'value_key': value_key,
                    'data': data_points,
                    'total': dataset_total,
                    'formatted_total': _format_number(dataset_total)
                })

            payload = {
                'labels': chart_labels,
                'datasets': formatted_datasets,
                'value_keys': list(result.value_labels),
                'display_mode': display_mode,
                'totals': {key: totals.get(key) for key in value_labels},
                'formatted_totals': {key: _format_number(totals.get(key)) for key in value_labels}
            }
            if axis_metadata:
                payload['axis'] = axis_metadata
            if time_axis_enabled:
                payload['display_labels'] = display_labels
            return payload

        totals: Dict[str, Optional[float]] = {label: 0.0 for label in value_labels}
        counts: Dict[str, int] = {label: 0 for label in value_labels}
        dataset_values: Dict[str, Dict[str, float]] = {label: {} for label in value_labels}

        for row in result.rows:
            primary_raw = row.get(primary_group_label) if primary_group_label else None
            label_key = remember_label(primary_raw)
            for value_label in value_labels:
                value = row.get(value_label)
                numeric_value = _ensure_numeric(value)
                if numeric_value is not None:
                    dataset_values.setdefault(value_label, {})[label_key] = numeric_value
                    totals[value_label] = (totals.get(value_label) or 0.0) + numeric_value
                    counts[value_label] = counts.get(value_label, 0) + 1
                else:
                    dataset_values.setdefault(value_label, {}).setdefault(label_key, 0)

        for value_label, count in counts.items():
            if count == 0:
                totals[value_label] = None

        if time_axis_enabled:
            label_entries.sort(key=lambda item: (_time_sort_key(item['raw']), item['display']))
            axis_metadata = {
                'type': 'time',
                'bucket': time_bucket,
                'display_labels': [entry['display'] for entry in label_entries]
            }
            if timeframe_start is not None and timeframe_end is not None:
                range_start = timeframe_start
                range_end = timeframe_end
                if time_bucket:
                    range_start = _floor_datetime_to_bucket(timeframe_start, time_bucket)
                    end_floor = _floor_datetime_to_bucket(timeframe_end, time_bucket)
                    next_end = _advance_datetime_by_bucket(end_floor, time_bucket)
                    range_end = next_end if next_end > end_floor else end_floor
                axis_metadata['range'] = {
                    'start': range_start.isoformat(),
                    'end': range_end.isoformat()
                }

        label_order_keys = [entry['key'] for entry in label_entries]
        display_labels = [entry['display'] for entry in label_entries]
        chart_labels = label_order_keys if time_axis_enabled else display_labels

        formatted_datasets: List[Dict[str, Any]] = []
        for value_label in value_labels:
            values_dict = dataset_values.get(value_label, {})
            values = [values_dict.get(label_key, 0) for label_key in label_order_keys]
            formatted_datasets.append({
                'label': _capitalize_label(value_label),
                'value_key': value_label,
                'data': values,
                'total': totals.get(value_label),
                'formatted_total': _format_number(totals.get(value_label))
            })

        payload = {
            'labels': chart_labels,
            'datasets': formatted_datasets,
            'value_keys': list(result.value_labels),
            'display_mode': display_mode,
            'totals': {key: totals.get(key) for key in value_labels},
            'formatted_totals': {key: _format_number(totals.get(key)) for key in value_labels}
        }
        if axis_metadata:
            payload['axis'] = axis_metadata
        if time_axis_enabled:
            payload['display_labels'] = display_labels
        return payload

    if chart_type in {'number', 'percentage'}:
        numerator_key = options.get('percentage_numerator') or options.get('percentageNumerator')
        denominator_key = options.get('percentage_denominator') or options.get('percentageDenominator')
        label_override = options.get('percentage_label') or options.get('percentageLabel')

        value_label = result.value_labels[0] if result.value_labels else None
        value = None
        numerator_raw = None
        denominator_raw = None

        if numerator_key and result.rows:
            numerator_raw = result.rows[0].get(numerator_key)
        if denominator_key and result.rows:
            denominator_raw = result.rows[0].get(denominator_key)

        if numerator_key and denominator_key:
            numerator_value = _ensure_numeric(numerator_raw)
            denominator_value = _ensure_numeric(denominator_raw)
            if numerator_value is not None and denominator_value not in (None, 0):
                value = (numerator_value / denominator_value) * 100.0
            else:
                value = None
            value_label = numerator_key
        else:
            if result.rows:
                value = result.rows[0].get(value_label) if value_label else None

        numeric_value = _ensure_numeric(value)
        formatted_value = _format_number(value)
        formatted_percentage = _format_percentage(numeric_value if numeric_value is not None else None)

        label_text = label_override or (_capitalize_label(value_label) if value_label else '')

        payload = {
            'value': value,
            'label': label_text,
            'rows': result.rows,
            'display_mode': display_mode,
            'formatted_value': formatted_value,
            'formatted_percentage': formatted_percentage
        }

        if numerator_key and denominator_key:
            payload['source_values'] = {
                'numerator': numerator_raw,
                'denominator': denominator_raw,
                'numerator_key': numerator_key,
                'denominator_key': denominator_key
            }

        if chart_type == 'percentage':
            payload['formatted_value'] = formatted_percentage

        return payload

    if chart_type == 'table':
        select_labels = list(result.select_labels) if result.select_labels else []
        group_keys: List[str] = []
        value_keys: List[str] = []
        group_label_set = set(result.group_labels)

        for label in select_labels:
            if label in group_label_set and label not in group_keys:
                group_keys.append(label)
            elif label not in value_keys:
                value_keys.append(label)

        for label in result.group_labels:
            if label not in group_keys:
                group_keys.append(label)

        for label in result.value_labels:
            if label not in group_label_set and label not in value_keys:
                value_keys.append(label)

        if not value_keys and result.rows:
            for key in result.rows[0].keys():
                if key not in group_keys and key not in value_keys:
                    value_keys.append(key)

        totals: Dict[str, Optional[float]] = {key: 0.0 for key in value_keys}
        counts: Dict[str, int] = {key: 0 for key in value_keys}

        for row in result.rows:
            for key in value_keys:
                numeric_value = _ensure_numeric(row.get(key))
                if numeric_value is not None:
                    totals[key] = (totals.get(key) or 0.0) + numeric_value
                    counts[key] = counts.get(key, 0) + 1

        for key, count in counts.items():
            if count == 0:
                totals[key] = None

        table_rows: List[Dict[str, Any]] = []
        for row in result.rows:
            group_values = [row.get(key) for key in group_keys]
            formatted_group_values = [_format_group_value(row.get(key)) for key in group_keys]
            value_cells = []
            for key in value_keys:
                raw_value = row.get(key)
                numeric_value = _ensure_numeric(raw_value)
                total_value = totals.get(key)
                percentage_value: Optional[float] = None
                if numeric_value is not None and total_value not in (None, 0):
                    percentage_value = (numeric_value / total_value) * 100
                elif numeric_value is not None and total_value == 0:
                    percentage_value = 0.0

                value_cells.append({
                    'key': key,
                    'value': raw_value,
                    'formatted_value': _format_number(raw_value),
                    'percentage': percentage_value,
                    'formatted_percentage': _format_percentage(percentage_value)
                    if percentage_value is not None else '--'
                })

            table_rows.append({
                'group_values': group_values,
                'formatted_group_values': formatted_group_values,
                'value_cells': value_cells
            })

        totals_entries = []
        for key in value_keys:
            total_value = totals.get(key)
            if total_value is None and counts.get(key, 0) == 0:
                formatted_percentage = '--'
                percentage_value = None
            elif total_value == 0:
                percentage_value = 0.0
                formatted_percentage = _format_percentage(0.0)
            else:
                percentage_value = 100.0 if total_value is not None else None
                formatted_percentage = _format_percentage(percentage_value) if percentage_value is not None else '--'

            totals_entries.append({
                'key': key,
                'value': total_value,
                'formatted_value': _format_number(total_value),
                'percentage': percentage_value,
                'formatted_percentage': formatted_percentage
            })

        return {
            'display_mode': display_mode,
            'group_headers': [_capitalize_label(key) for key in group_keys],
            'value_headers': [_capitalize_label(key) for key in value_keys],
            'group_keys': group_keys,
            'value_keys': value_keys,
            'rows': table_rows,
            'totals': totals_entries,
            'total_label': options.get('total_label') or 'Total',
            'source_rows': result.rows
        }

    return {
        'rows': result.rows,
        'group_labels': result.group_labels,
        'value_labels': result.value_labels
    }
