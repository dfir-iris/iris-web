from __future__ import annotations

import copy
import uuid
from typing import Iterable, List, Optional

from sqlalchemy import or_, select

from app import db
from app.models.custom_dashboard import CustomDashboard, CustomDashboardWidget


class DashboardAccessError(Exception):
    pass


class DashboardNotFoundError(Exception):
    pass


class DashboardSystemReadOnlyError(Exception):
    pass


def list_dashboards_for_user(user_id: int) -> List[CustomDashboard]:
    stmt = select(CustomDashboard).where(
        or_(
            CustomDashboard.owner_id == user_id,
            CustomDashboard.is_shared.is_(True),
            CustomDashboard.is_system.is_(True),
        )
    ).order_by(CustomDashboard.is_system.desc(), CustomDashboard.created_at.desc())
    return list(db.session.execute(stmt).scalars().all())


def get_dashboard_by_uuid(dashboard_uuid: str) -> Optional[CustomDashboard]:
    stmt = select(CustomDashboard).where(CustomDashboard.dashboard_uuid == dashboard_uuid)
    return db.session.execute(stmt).scalar_one_or_none()


def get_dashboard_for_user(dashboard_uuid: str, user_id: int) -> CustomDashboard:
    dashboard = get_dashboard_by_uuid(dashboard_uuid)
    if dashboard is None:
        raise DashboardNotFoundError()

    if dashboard.is_system or dashboard.is_shared:
        return dashboard
    if dashboard.owner_id != user_id:
        raise DashboardAccessError()
    return dashboard


def _resolve_shared_flag(data: dict) -> bool:
    value = data.get('is_shared')
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {'true', '1', 'yes', 'on'}
    if isinstance(value, int):
        return value != 0
    return False


def _prepare_dashboard_payload(data: dict) -> List[dict]:
    sections_payload = data.get('sections') or []
    widgets_payload = data.get('widgets') or []

    normalized_sections = []
    flattened_widgets: List[dict] = []

    if sections_payload:
        for section_index, raw_section in enumerate(sections_payload):
            section = copy.deepcopy(raw_section or {})
            section_id = section.get('id') or f'section-{uuid.uuid4()}'
            section['id'] = section_id
            section_title = section.get('title')
            section_description = section.get('description')
            show_divider = bool(section.get('show_divider'))

            normalized_widgets = []
            for widget_index, raw_widget in enumerate(section.get('widgets') or []):
                widget = copy.deepcopy(raw_widget or {})
                layout = dict(widget.get('layout') or {})
                layout.setdefault('section_id', section_id)
                layout.setdefault('section_title', section_title)
                layout.setdefault('section_description', section_description)
                layout.setdefault('section_index', section_index)
                layout.setdefault('widget_index', widget_index)
                layout.setdefault('show_divider', show_divider)

                options = widget.get('options') if isinstance(widget.get('options'), dict) else {}
                if options and not layout.get('widget_size'):
                    candidate_size = options.get('widget_size') or options.get('size')
                    if candidate_size:
                        layout['widget_size'] = candidate_size

                widget['layout'] = layout
                normalized_widgets.append(widget)
                flattened_widgets.append(widget)

            section['widgets'] = normalized_widgets
            normalized_sections.append(section)
    else:
        default_section_id = f'section-{uuid.uuid4()}'
        default_section_title = data.get('name')
        default_section_description = data.get('description')
        default_section = {
            'id': default_section_id,
            'title': default_section_title,
            'description': default_section_description,
            'show_divider': False,
            'widgets': []
        }

        for widget_index, raw_widget in enumerate(widgets_payload):
            widget = copy.deepcopy(raw_widget or {})
            layout = dict(widget.get('layout') or {})
            layout.setdefault('section_id', default_section_id)
            layout.setdefault('section_title', default_section_title)
            layout.setdefault('section_description', default_section_description)
            layout.setdefault('section_index', 0)
            layout.setdefault('widget_index', widget_index)
            layout.setdefault('show_divider', False)

            options = widget.get('options') if isinstance(widget.get('options'), dict) else {}
            if options and not layout.get('widget_size'):
                candidate_size = options.get('widget_size') or options.get('size')
                if candidate_size:
                    layout['widget_size'] = candidate_size

            widget['layout'] = layout
            default_section['widgets'].append(widget)
            flattened_widgets.append(widget)

        normalized_sections.append(default_section)

    data['sections'] = normalized_sections
    data['widgets'] = flattened_widgets
    return flattened_widgets


def create_dashboard_for_user(user_id: int, payload: dict, allow_share: bool) -> CustomDashboard:
    data = dict(payload or {})
    data.pop('csrf_token', None)
    is_shared = _resolve_shared_flag(data) if allow_share else False
    data['is_shared'] = is_shared

    _prepare_dashboard_payload(data)

    dashboard = CustomDashboard(
        name=data['name'],
        description=data.get('description'),
        owner_id=user_id,
        is_shared=is_shared,
        is_system=False,
        definition=data,
    )
    _apply_widgets(dashboard, data.get('widgets', []))
    db.session.add(dashboard)
    db.session.commit()
    return dashboard


def update_dashboard_for_user(dashboard_uuid: str, user_id: int, payload: dict, allow_share: bool) -> CustomDashboard:
    dashboard = get_dashboard_for_user(dashboard_uuid, user_id)
    if dashboard.is_system:
        raise DashboardSystemReadOnlyError()
    if dashboard.owner_id != user_id:
        raise DashboardAccessError()

    data = dict(payload or {})
    data.pop('csrf_token', None)
    requested_shared = _resolve_shared_flag(data) if allow_share else dashboard.is_shared
    data['is_shared'] = requested_shared

    _prepare_dashboard_payload(data)

    dashboard.name = data.get('name', dashboard.name)
    dashboard.description = data.get('description', dashboard.description)
    dashboard.is_shared = requested_shared
    dashboard.definition = data
    dashboard.widgets.clear()
    _apply_widgets(dashboard, data.get('widgets', []))
    db.session.commit()
    return dashboard


def delete_dashboard_for_user(dashboard_uuid: str, user_id: int) -> None:
    dashboard = get_dashboard_for_user(dashboard_uuid, user_id)
    if dashboard.is_system:
        raise DashboardSystemReadOnlyError()
    if dashboard.owner_id != user_id:
        raise DashboardAccessError()

    db.session.delete(dashboard)
    db.session.commit()


def _apply_widgets(dashboard: CustomDashboard, widgets_payload: Iterable[dict]) -> None:
    for position, widget in enumerate(widgets_payload):
        dashboard.widgets.append(CustomDashboardWidget(
            name=widget['name'],
            chart_type=widget['chart_type'],
            definition=widget,
            position=position,
        ))


def serialize_dashboard(dashboard: CustomDashboard) -> dict:
    return {
        'dashboard_uuid': str(dashboard.dashboard_uuid),
        'name': dashboard.name,
        'description': dashboard.description,
        'owner_id': dashboard.owner_id,
        'is_shared': dashboard.is_shared,
        'is_system': dashboard.is_system,
        'definition': dashboard.definition or {},
        'created_at': dashboard.created_at.isoformat() if dashboard.created_at else None,
        'updated_at': dashboard.updated_at.isoformat() if dashboard.updated_at else None,
    }
