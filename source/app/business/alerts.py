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

import json
from datetime import datetime

from app import db
from app import socket_io
from app.models.alerts import Alert
from app.models.iocs import Ioc
from app.models.models import CaseAssets
from app.datamgmt.alerts.alerts_db import cache_similar_alert
from app.datamgmt.alerts.alerts_db import delete_similar_alert_cache
from app.datamgmt.alerts.alerts_db import delete_related_alerts_cache
from app.datamgmt.alerts.alerts_db import get_alert_by_id
from app.datamgmt.alerts.alerts_db import delete_alert
from app.datamgmt.alerts.alerts_db import get_related_alerts
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.util import add_obj_history_entry
from app.business.errors import ObjectNotFoundError
from app.datamgmt.manage.manage_access_control_db import user_has_client_access


def alerts_create(alert: Alert, iocs: list[Ioc], assets: list[CaseAssets]) -> Alert:

    alert.alert_creation_time = datetime.utcnow()

    alert.iocs = iocs
    alert.assets = assets

    db.session.add(alert)
    db.session.commit()

    add_obj_history_entry(alert, 'Alert created')

    cache_similar_alert(alert.alert_customer_id, assets, iocs, alert.alert_id, alert.alert_source_event_time)

    alert = call_modules_hook('on_postload_alert_create', data=alert)

    track_activity(f"created alert #{alert.alert_id} - {alert.alert_title}", ctx_less=True)

    socket_io.emit('new_alert', json.dumps({
        'alert_id': alert.alert_id
    }), namespace='/alerts')

    return alert


def alerts_get(current_user, identifier) -> Alert:

    alert = get_alert_by_id(identifier)

    if not alert:
        raise ObjectNotFoundError()
    if not user_has_client_access(current_user.id, alert.alert_customer_id):
        raise ObjectNotFoundError()

    return alert


def alerts_update(alert: Alert, updated_alert: Alert, activity_data) -> Alert:

    do_resolution_hook = False
    do_status_hook = False

    if alert.alert_resolution_status_id != updated_alert.alert_resolution_status_id:
        do_resolution_hook = True
    if alert.alert_status_id != updated_alert.alert_status_id:
        do_status_hook = True

    updated_alert = call_modules_hook('on_postload_alert_update', data=updated_alert)

    if do_resolution_hook:
        updated_alert = call_modules_hook('on_postload_alert_resolution_update', data=updated_alert)

    if do_status_hook:
        updated_alert = call_modules_hook('on_postload_alert_status_update', data=updated_alert)

    if activity_data:
        activity_data_as_string = ','.join(activity_data)
        track_activity(f'updated alert #{alert.alert_id}: {activity_data_as_string}', ctx_less=True)
        add_obj_history_entry(updated_alert, f'updated alert: {activity_data_as_string}')
    else:
        track_activity(f'updated alert #{alert.alert_id}', ctx_less=True)
        add_obj_history_entry(updated_alert, 'updated alert')

    db.session.commit()
    return updated_alert


def alerts_delete(alert: Alert):

    delete_similar_alert_cache(alert.alert_id)
    delete_related_alerts_cache([alert.alert_id])
    delete_alert(alert)

    call_modules_hook('on_postload_alert_delete', data=alert.alert_id)

    track_activity(f"delete alert #{alert.alert_id}", ctx_less=True)


def alerts_related(alert: Alert):

        similarities = get_related_alerts(alert.alert_customer_id, alert.assets, alert.iocs)
        return similarities
