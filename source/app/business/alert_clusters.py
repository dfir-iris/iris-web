#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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
from typing import Iterable
from typing import List
from typing import Optional

from app.blueprints.iris_user import iris_current_user
from app.business.access_controls import access_controls_user_has_customer_access
from app.datamgmt.alerts.alerts_db import create_case_from_alerts
from app.datamgmt.alerts.alerts_db import merge_alert_in_case
from app.datamgmt.case.case_db import get_case
from app.db import db
from app.iris_engine.access_control.utils import ac_set_new_case_access
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.alerts import Alert
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.alerts import AlertStatus
from app.models.alert_clusters import AlertCluster
from app.models.alert_clusters import AlertClusterStatus
from app.util import add_obj_history_entry


# Fields whose changes are worth pinning to the analyst activity trail —
# status, owner, severity, title. Description edits generate a lot of
# small revisions (typos, formatting) so we keep them out to avoid
# flooding the timeline; the analyst still sees the current text on the
# detail page.
_AUDITED_FIELDS = {
    'cluster_status_id': 'status',
    'cluster_owner_id': 'owner',
    'cluster_severity_id': 'severity',
    'cluster_title': 'title',
}


# Public status-name constants. Kept as module-level names so callers
# in other modules can reference them without either duplicating the
# literal string (drift risk) or reaching into an underscored private
# (lint violation). The `_STATUS_*` aliases below are kept for the
# in-file callers.
CLUSTER_STATUS_OPEN = 'Open'
CLUSTER_STATUS_INVESTIGATING = 'Investigating'
CLUSTER_STATUS_DISMISSED = 'Dismissed'
CLUSTER_STATUS_ESCALATED = 'Escalated'

_STATUS_OPEN = CLUSTER_STATUS_OPEN
_STATUS_INVESTIGATING = CLUSTER_STATUS_INVESTIGATING
_STATUS_DISMISSED = CLUSTER_STATUS_DISMISSED
_STATUS_ESCALATED = CLUSTER_STATUS_ESCALATED


def resolve_status_id(status_name: str) -> int:
    """Look up an `AlertClusterStatus.status_id` by its human-readable name.

    Public so other business modules (e.g. `cluster_rules._apply_create_cluster`)
    can resolve the "Open" status when opening a new cluster, without
    reaching into a private helper — Ruff / import-linters flag cross-
    module private imports and the underscore signals module-internal
    intent."""
    status = AlertClusterStatus.query.filter_by(status_name=status_name).first()
    if not status:
        raise BusinessProcessingError(f'AlertClusterStatus "{status_name}" is not seeded')
    return status.status_id


# Backwards-compatible alias — this file's own callers used `_status_id`
# before the rename; keep the alias so no in-file caller changes.
_status_id = resolve_status_id


# Cluster -> alert status mapping applied whenever the cluster's status
# is updated. Chosen so that the alert timeline mirrors what the analyst
# is doing at the cluster level:
#   Open          -> "Assigned"      (someone owns this cluster)
#   Investigating -> "In progress"   (active work)
#   Dismissed     -> "Closed"        (no action taken)
# The `Escalated` cluster status is NOT in this map: the escalate/merge
# flows already set alerts to `Escalated` (new case) or `Merged`
# (existing case) explicitly, and letting the generic propagator run
# afterwards would clobber that distinction.
_CLUSTER_TO_ALERT_STATUS = {
    CLUSTER_STATUS_OPEN: 'Assigned',
    CLUSTER_STATUS_INVESTIGATING: 'In progress',
    CLUSTER_STATUS_DISMISSED: 'Closed',
}


def _resolve_alert_status_id(status_name: str) -> Optional[int]:
    """Look up an `AlertStatus.status_id` by name. Returns None (with a
    log line) if the seed row is missing so the caller can degrade to a
    no-op rather than 500ing on a status change."""
    row = AlertStatus.query.filter_by(status_name=status_name).first()
    if row is None:
        from app.logger import logger
        logger.warning('AlertStatus "%s" is not seeded; cannot propagate', status_name)
        return None
    return row.status_id


def _propagate_status_to_alerts(cluster: AlertCluster, new_status_name: str) -> None:
    """Push the cluster's new status down to every member alert according to
    `_CLUSTER_TO_ALERT_STATUS`. No-op for status transitions we don't map
    (e.g. `Escalated` — see the mapping doc above). The caller is
    responsible for committing; we only mutate ORM state so the outer
    transaction stays a single commit."""
    target_alert_status = _CLUSTER_TO_ALERT_STATUS.get(new_status_name)
    if target_alert_status is None:
        return
    alert_status_id = _resolve_alert_status_id(target_alert_status)
    if alert_status_id is None:
        return
    changed = 0
    for alert in cluster.alerts:
        if alert.alert_status_id != alert_status_id:
            alert.alert_status_id = alert_status_id
            changed += 1
    if changed:
        add_obj_history_entry(
            cluster,
            f'propagated status to {changed} alert(s) as {target_alert_status!r}',
        )


def alert_clusters_create(cluster: AlertCluster) -> AlertCluster:
    if cluster.cluster_status_id is None:
        cluster.cluster_status_id = _status_id(_STATUS_OPEN)
    cluster.cluster_creation_time = datetime.utcnow()
    db.session.add(cluster)
    db.session.commit()
    add_obj_history_entry(cluster, 'created', commit=True)
    track_activity(f'created alert cluster #{cluster.cluster_id} - {cluster.cluster_title}', ctx_less=True)
    _enqueue_flow_evaluation(cluster.cluster_id)
    cluster = call_modules_hook('on_postload_alert_cluster_create', cluster)
    return cluster


def _enqueue_flow_evaluation(cluster_id: int) -> None:
    """Fire the async flow evaluator against a newly created / updated
    cluster. Import is deferred and errors are swallowed — a broken
    worker must not block cluster writes on the request path."""
    try:
        from app.iris_engine.cluster_rules.tasks import evaluate_alert_cluster_flows
        evaluate_alert_cluster_flows.delay(cluster_id)
    except Exception:  # noqa: BLE001
        from app.logger import logger
        logger.exception('Failed to enqueue flow evaluation for alert cluster #%s', cluster_id)


def alert_clusters_get(user, permissions, identifier, fallback_customer_access=None) -> AlertCluster:
    cluster = AlertCluster.query.filter_by(cluster_id=identifier).first()
    if not cluster:
        raise ObjectNotFoundError()
    if not access_controls_user_has_customer_access(
        user, permissions, cluster.cluster_customer_id,
        fallback_customer_access=fallback_customer_access
    ):
        raise ObjectNotFoundError()
    return cluster


def alert_clusters_get_by_case(case_id: int) -> Optional[AlertCluster]:
    """Return the cluster this case was created from (via escalate/merge),
    or None if the case wasn't sourced from a cluster. Powers the "back
    to source cluster" chip in the case topbar; callers must gate access
    on the case, not the cluster — anyone who can read the case can see
    which cluster it came from.
    """
    return AlertCluster.query.filter_by(cluster_case_id=case_id).first()


def alert_clusters_search(customer_id: Optional[int], status_id: Optional[int],
                          title: Optional[str], user_identifier_filter: Optional[int],
                          page: int, per_page: int, sort: Optional[str]):
    """Paginated cluster search. `user_identifier_filter` = None means
    server-admin (see all). Otherwise scope by the caller's UserClient rows —
    same pattern `get_filtered_alerts` uses for tenant isolation."""
    from app.models.authorization import UserClient  # local import to avoid cycles

    query = AlertCluster.query
    if user_identifier_filter is not None:
        accessible = db.session.query(UserClient.client_id).filter(
            UserClient.user_id == user_identifier_filter
        ).subquery()
        query = query.filter(AlertCluster.cluster_customer_id.in_(accessible))
    if customer_id is not None:
        query = query.filter(AlertCluster.cluster_customer_id == customer_id)
    if status_id is not None:
        query = query.filter(AlertCluster.cluster_status_id == status_id)
    if title:
        query = query.filter(AlertCluster.cluster_title.ilike(f'%{title}%'))

    direction = 'desc'
    if sort and sort.endswith(' asc'):
        direction = 'asc'
    if direction == 'asc':
        query = query.order_by(AlertCluster.cluster_creation_time.asc())
    else:
        query = query.order_by(AlertCluster.cluster_creation_time.desc())

    return query.paginate(page=page, per_page=per_page, error_out=False)


def alert_clusters_update(cluster: AlertCluster, changes: dict) -> AlertCluster:
    # Snapshot before-values for audited fields so we can record the
    # transition into modification_history. Reading via getattr after
    # setattr would already show the new value.
    audit_before = {
        key: getattr(cluster, key, None)
        for key in _AUDITED_FIELDS
        if key in changes
    }
    status_changed = (
        'cluster_status_id' in changes
        and audit_before.get('cluster_status_id') != changes['cluster_status_id']
    )
    for key, value in changes.items():
        setattr(cluster, key, value)
    for key, label in _AUDITED_FIELDS.items():
        if key not in changes:
            continue
        old_value = audit_before.get(key)
        new_value = getattr(cluster, key, None)
        if old_value == new_value:
            continue
        add_obj_history_entry(
            cluster,
            f'changed {label}: {old_value!r} -> {new_value!r}',
        )
    # Cascade the cluster's new status onto its member alerts (see
    # `_CLUSTER_TO_ALERT_STATUS`). Skipped when the status didn't
    # actually move so re-saving the same status doesn't spam alert
    # history. `Escalated` is intentionally not in the mapping — the
    # escalate/merge flows set alert status themselves.
    if status_changed and cluster.status is not None:
        _propagate_status_to_alerts(cluster, cluster.status.status_name)
    db.session.commit()
    track_activity(f'updated alert cluster #{cluster.cluster_id}', ctx_less=True)
    _enqueue_flow_evaluation(cluster.cluster_id)
    cluster = call_modules_hook('on_postload_alert_cluster_update', cluster)
    return cluster


def alert_clusters_delete(cluster: AlertCluster) -> None:
    identifier = cluster.cluster_id
    db.session.delete(cluster)
    db.session.commit()
    track_activity(f'deleted alert cluster #{identifier}', ctx_less=True)
    call_modules_hook('on_postload_alert_cluster_delete', identifier)


def alert_cluster_add_alerts(cluster: AlertCluster, alert_ids: Iterable[int]) -> AlertCluster:
    """Attach alerts to a cluster. Silently skips alerts already attached and
    alerts belonging to a different customer than the cluster — mixing tenants
    inside a container would leak data through `cluster.alerts`."""
    ids = list(alert_ids)
    if not ids:
        return cluster
    alerts = Alert.query.filter(
        Alert.alert_id.in_(ids),
        Alert.alert_customer_id == cluster.cluster_customer_id
    ).all()
    existing = {a.alert_id for a in cluster.alerts}
    added_ids = []
    for alert in alerts:
        if alert.alert_id not in existing:
            cluster.alerts.append(alert)
            added_ids.append(alert.alert_id)
    if added_ids:
        add_obj_history_entry(cluster, f'linked alerts: {added_ids}')
    db.session.commit()
    if added_ids:
        call_modules_hook('on_postload_alert_cluster_alert_add',
                          {'cluster_id': cluster.cluster_id,
                           'alert_ids': added_ids})
    return cluster


def alert_cluster_remove_alert(cluster: AlertCluster, alert_id: int) -> AlertCluster:
    was_linked = any(a.alert_id == alert_id for a in cluster.alerts)
    if was_linked:
        cluster.alerts = [a for a in cluster.alerts if a.alert_id != alert_id]
        add_obj_history_entry(cluster, f'unlinked alert #{alert_id}')
    db.session.commit()
    if was_linked:
        call_modules_hook('on_postload_alert_cluster_alert_remove',
                          {'cluster_id': cluster.cluster_id,
                           'alert_id': alert_id})
    return cluster


def alert_cluster_escalate_to_case(cluster: AlertCluster, template_id: Optional[int] = None,
                                   case_title: Optional[str] = None, note: Optional[str] = None,
                                   import_as_event: bool = False, case_tags: str = ''):
    """Escalate the cluster to a case. Reuses `create_case_from_alerts` so the
    case gets all member alerts linked (plus their IOCs/assets), which is what
    the existing alerts-to-case flow already does. Idempotent-ish: re-escalating
    a linked cluster raises, callers should check `cluster_case_id` first."""
    if cluster.cluster_case_id is not None:
        raise BusinessProcessingError('Alert cluster already escalated to a case')
    if not cluster.alerts:
        raise BusinessProcessingError('Cannot escalate a cluster with no alerts')

    # `create_case_from_alerts` matches IOCs/assets by UUID, not id.
    # Passing numeric ids here silently drops every IOC/asset from the
    # linked case, which is the "escalation produces an empty case"
    # behaviour we're fixing alongside the ACL grant below.
    case = create_case_from_alerts(
        alerts=list(cluster.alerts),
        iocs_list=[str(i.ioc_uuid) for a in cluster.alerts for i in (a.iocs or [])],
        assets_list=[str(a2.asset_uuid) for a in cluster.alerts for a2 in (a.assets or [])],
        case_title=case_title or cluster.cluster_title,
        note=note or cluster.cluster_description or '',
        import_as_event=import_as_event,
        case_tags=case_tags,
        template_id=template_id,
    )

    # Grant the escalating user access to the freshly created case. Without
    # this the case row lives in the DB but is filtered out of every
    # per-user query (`user_list_cases_view`), so from the analyst's point
    # of view the escalation "consumes" a case id and produces nothing.
    # Mirrors the alert-escalation flow in `alerts_routes.py:642`.
    ac_set_new_case_access(iris_current_user, case.case_id, case.client_id)

    # Fire the same post-create module hook and history entry the normal
    # alert-escalate path fires — modules that react to new cases (SLA
    # trackers, external syncs) shouldn't have to special-case clusters.
    case = call_modules_hook('on_postload_case_create', case)
    add_obj_history_entry(case, 'created')

    cluster.cluster_case_id = case.case_id
    cluster.cluster_status_id = _status_id(_STATUS_ESCALATED)
    # Mark every member alert as Escalated so the alerts board reflects
    # the cluster-level decision. Uses the same seed-lookup helper the
    # alert-escalate route uses (`alerts_routes.py:631`).
    escalated_alert_id = _resolve_alert_status_id('Escalated')
    if escalated_alert_id is not None:
        for alert in cluster.alerts:
            if alert.alert_status_id != escalated_alert_id:
                alert.alert_status_id = escalated_alert_id
    add_obj_history_entry(cluster, f'escalated to case #{case.case_id}')
    db.session.commit()
    track_activity(
        f'escalated alert cluster #{cluster.cluster_id} to case #{case.case_id}',
        ctx_less=True,
    )
    call_modules_hook('on_postload_alert_cluster_escalate',
                      {'cluster_id': cluster.cluster_id,
                       'case_id': case.case_id},
                      caseid=case.case_id)
    return case


def alert_cluster_merge_to_case(cluster: AlertCluster, target_case_id: int,
                                note: Optional[str] = None, import_as_event: bool = False,
                                case_tags: str = ''):
    """Merge a cluster's alerts into an already-existing case. Analogous to
    the alerts-to-existing-case merge flow (`alerts_routes.py:667`), but
    fanned out across every alert on the cluster: each alert links to the
    target case, its selected IOCs/assets get imported, and the cluster
    is marked Escalated + backpointed to the target case.

    Same guardrails as escalate: re-merging a linked cluster raises, and
    a cluster with no alerts has nothing to merge. The caller is
    responsible for gating access to `target_case_id` — the request-layer
    endpoint checks case access before calling in.
    """
    if cluster.cluster_case_id is not None:
        raise BusinessProcessingError('Alert cluster already linked to a case')
    if not cluster.alerts:
        raise BusinessProcessingError('Cannot merge a cluster with no alerts')

    case = get_case(target_case_id)
    if case is None:
        raise BusinessProcessingError(f'Target case #{target_case_id} not found')
    if case.client_id != cluster.cluster_customer_id:
        raise BusinessProcessingError(
            'Target case belongs to a different customer than the cluster'
        )

    # Import every alert's IOCs and assets into the case. `merge_alert_in_case`
    # dedupes by (value,type) for IOCs and (name,type) for assets so
    # re-merging alerts that share indicators doesn't create duplicates.
    alerts_snapshot = list(cluster.alerts)
    for alert in alerts_snapshot:
        merge_alert_in_case(
            alert=alert,
            case=case,
            iocs_list=[str(i.ioc_uuid) for i in (alert.iocs or [])],
            assets_list=[str(a.asset_uuid) for a in (alert.assets or [])],
            note=note or cluster.cluster_description or '',
            import_as_event=import_as_event,
            case_tags=case_tags,
        )

    cluster.cluster_case_id = case.case_id
    cluster.cluster_status_id = _status_id(_STATUS_ESCALATED)
    # Mark every member alert as Merged (not Escalated) — the alert-merge
    # route does the same thing at `alerts_routes.py:710`.
    merged_alert_id = _resolve_alert_status_id('Merged')
    if merged_alert_id is not None:
        for alert in cluster.alerts:
            if alert.alert_status_id != merged_alert_id:
                alert.alert_status_id = merged_alert_id
    add_obj_history_entry(cluster, f'merged into case #{case.case_id}')
    db.session.commit()
    track_activity(
        f'merged alert cluster #{cluster.cluster_id} into case #{case.case_id}',
        ctx_less=True,
    )
    # Best-effort hook fire. `call_modules_hook` raises when the hook name
    # isn't seeded in `iris_hooks` (post_init seeds it on boot); we don't
    # want a fresh install / mid-upgrade instance to 500 the whole merge
    # because a module hook row hasn't landed yet. The merge itself is
    # already committed above, so swallowing here just means module
    # listeners miss THIS event — the operation is otherwise complete.
    try:
        call_modules_hook('on_postload_alert_cluster_merge',
                          {'cluster_id': cluster.cluster_id,
                           'case_id': case.case_id},
                          caseid=case.case_id)
    except Exception:  # noqa: BLE001
        from app.logger import logger
        logger.exception('on_postload_alert_cluster_merge hook failed; merge already committed')
    return case


def alert_cluster_correlation_graph(cluster: AlertCluster) -> dict:
    """Build a correlation graph (nodes + edges) for the cluster.

    Nodes are one of three kinds:
      * `alert`  — one per member alert
      * `ioc`    — deduplicated by (value, type_id) across every alert
      * `asset`  — deduplicated by (name, type_id) across every alert
    Edges connect each alert to every IOC / asset it carries. Dedup keys
    let a single IOC/asset connect to multiple alerts, which is exactly
    the correlation surface the graph exists to expose.

    Node shape matches `_create_*_node` in `business/alerts.py` closely
    enough that the frontend's `VisNetwork` component can render this
    payload with no per-source branching.
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    seen_iocs: dict[tuple[str, Optional[int]], str] = {}
    seen_assets: dict[tuple[str, Optional[int]], str] = {}

    for alert in cluster.alerts:
        alert_node_id = f'alert_{alert.alert_id}'
        status_name = alert.status.status_name if alert.status else ''
        is_closed = status_name in ('Closed', 'Merged', 'Escalated')
        label_prefix = '[Closed] ' if is_closed else ''
        nodes.append({
            'id': alert_node_id,
            'label': f'{label_prefix}{alert.alert_title}',
            'title': alert.alert_description or alert.alert_title,
            'group': 'alert',
        })

        for ioc in (alert.iocs or []):
            key = (ioc.ioc_value or '', ioc.ioc_type_id)
            node_id = seen_iocs.get(key)
            if node_id is None:
                node_id = f'ioc_{ioc.ioc_id}'
                seen_iocs[key] = node_id
                type_name = ioc.ioc_type.type_name if ioc.ioc_type else ''
                title_bits = [
                    f'<b>{ioc.ioc_value or ""}</b>',
                ]
                if type_name:
                    title_bits.append(f'type: {type_name}')
                if ioc.ioc_tags:
                    title_bits.append(f'tags: {ioc.ioc_tags}')
                nodes.append({
                    'id': node_id,
                    'label': ioc.ioc_value or f'ioc #{ioc.ioc_id}',
                    'title': '<br>'.join(title_bits),
                    'group': 'ioc',
                })
            edges.append({
                'from': alert_node_id,
                'to': node_id,
                'dashes': True,
            })

        for asset in (alert.assets or []):
            key = ((asset.asset_name or ''), asset.asset_type_id)
            node_id = seen_assets.get(key)
            if node_id is None:
                node_id = f'asset_{asset.asset_id}'
                seen_assets[key] = node_id
                type_name = asset.asset_type.asset_name if asset.asset_type else ''
                title_bits = [
                    f'<b>{asset.asset_name or ""}</b>',
                ]
                if type_name:
                    title_bits.append(f'type: {type_name}')
                if asset.asset_ip:
                    title_bits.append(f'ip: {asset.asset_ip}')
                if asset.asset_domain:
                    title_bits.append(f'domain: {asset.asset_domain}')
                asset_node = {
                    'id': node_id,
                    'label': asset.asset_name or f'asset #{asset.asset_id}',
                    'title': '<br>'.join(title_bits),
                    'group': 'asset',
                }
                # Include the asset-type icon path if the referenced asset
                # type carries one — mirrors what the alert graph does so
                # the client can pick a matching image without a second
                # lookup.
                icon = getattr(asset.asset_type, 'asset_icon_not_compromised', None)
                if icon:
                    asset_node['image'] = f'/static/assets/img/graph/{icon}'
                nodes.append(asset_node)
            edges.append({
                'from': alert_node_id,
                'to': node_id,
            })

    return {'nodes': nodes, 'edges': edges}


def alert_cluster_open_matching(customer_id: int, dedupe_key: str) -> Optional[AlertCluster]:
    """Look up an open cluster with the given dedupe key for stacking. Used by
    the rules engine when a rule action is create_cluster and its dedupe key
    matches a cluster already accepting alerts."""
    if not dedupe_key:
        return None
    open_status_id = _status_id(_STATUS_OPEN)
    investigating_status_id = _status_id(_STATUS_INVESTIGATING)
    return AlertCluster.query.filter(
        AlertCluster.cluster_customer_id == customer_id,
        AlertCluster.cluster_dedupe_key == dedupe_key,
        AlertCluster.cluster_status_id.in_([open_status_id, investigating_status_id]),
    ).order_by(AlertCluster.cluster_creation_time.desc()).first()
