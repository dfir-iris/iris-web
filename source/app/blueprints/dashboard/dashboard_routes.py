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

import json
from urllib.parse import urlencode

import marshmallow
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import logout_user
from flask_wtf import FlaskForm

from app import app
from app import db
from app import oidc_client
from app.datamgmt.dashboard.dashboard_db import get_global_task, list_user_cases, list_user_reviews
from app.datamgmt.dashboard.dashboard_db import get_tasks_status
from app.datamgmt.dashboard.dashboard_db import list_global_tasks
from app.datamgmt.dashboard.dashboard_db import list_user_tasks
from app.forms import CaseGlobalTaskForm
from app.iris_engine.access_control.utils import ac_get_user_case_counts
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import User
from app.models.cases import Cases
from app.models.alerts import Alert
from app.models.alerts import AlertCaseAssociation
from app.models.alerts import AlertResolutionStatus
from app.models.alerts import AlertStatus
from app.models.alerts import Severity
from app.models.models import CaseTasks
from app.models.models import GlobalTasks
from app.models.models import TaskStatus
from app.models.models import CaseStatus
from app.schema.marshables import CaseTaskSchema, CaseDetailsSchema
from app.schema.marshables import GlobalTasksSchema
from app.util import ac_api_requires, regenerate_session
from app.util import ac_requires_case_identifier
from app.util import ac_requires
from app.util import not_authenticated_redirection_url
from app.util import response_error
from app.util import response_success
from app.util import is_authentication_oidc

from sqlalchemy import func
from sqlalchemy import and_
from sqlalchemy import distinct

from oic.oauth2.exception import GrantError

log = app.logger


# CONTENT ------------------------------------------------
dashboard_blueprint = Blueprint(
    'index',
    __name__,
    template_folder='templates'
)


_TIMEFRAME_DEFAULT_DAYS = 30


def _parse_datetime_param(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)

    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    candidates = (
        raw,
        raw.replace('Z', '+00:00'),
    )

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed
        except ValueError:
            continue

    return None


def _resolve_timeframe(args):
    start_raw = args.get('start') or args.get('from')
    end_raw = args.get('end') or args.get('to')

    end_dt = _parse_datetime_param(end_raw)
    if end_raw and end_dt is None:
        raise ValueError('Invalid end timeframe value')

    start_dt = _parse_datetime_param(start_raw)
    if start_raw and start_dt is None:
        raise ValueError('Invalid start timeframe value')

    if end_dt is None:
        end_dt = datetime.utcnow()

    if start_dt is None:
        start_dt = end_dt - timedelta(days=_TIMEFRAME_DEFAULT_DAYS)

    if start_dt > end_dt:
        raise ValueError('Start timeframe must be earlier than end timeframe')

    return start_dt, end_dt


def _safe_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)

    if isinstance(value, str):
        return _parse_datetime_param(value)

    if hasattr(value, 'isoformat'):
        try:
            return _parse_datetime_param(value.isoformat())
        except Exception:
            return None

    return None


def _extract_custom_timestamp(custom_attributes, keys):
    if not custom_attributes:
        return None

    data = custom_attributes
    if isinstance(custom_attributes, str):
        try:
            data = json.loads(custom_attributes)
        except ValueError:
            return None

    if not isinstance(data, dict):
        return None

    for key in keys:
        if key in data:
            dt = _safe_datetime(data.get(key))
            if dt:
                return dt

    return None


def _extract_history_timestamp(history, keywords):
    if not history:
        return None

    data = history
    if isinstance(history, str):
        try:
            data = json.loads(history)
        except ValueError:
            return None

    if not isinstance(data, dict):
        return None

    matches = []

    for ts_raw, details in data.items():
        action = ''
        if isinstance(details, dict):
            action = details.get('action', '') or ''
        else:
            action = str(details)

        action_lower = action.lower()
        if not any(keyword in action_lower for keyword in keywords):
            continue

        try:
            ts_float = float(ts_raw)
        except (TypeError, ValueError):
            continue

        matches.append(datetime.fromtimestamp(ts_float, tz=timezone.utc).replace(tzinfo=None))

    if not matches:
        return None

    return min(matches)


def _get_case_phase_timestamp(case_obj, keywords, custom_keys):
    ts = _extract_custom_timestamp(case_obj.custom_attributes, custom_keys)
    if ts:
        return ts

    return _extract_history_timestamp(case_obj.modification_history, keywords)


def _average_seconds(durations):
    values = [delta.total_seconds() for delta in durations if delta is not None]
    if not values:
        return None

    return sum(values) / len(values)


def _duration_payload(avg_seconds):
    if avg_seconds is None:
        return {
            'seconds': None,
            'hours': None
        }

    hours = avg_seconds / 3600
    return {
        'seconds': avg_seconds,
        'hours': hours
    }


def _percentage(numerator, denominator):
    if denominator in (None, 0):
        return None

    return (numerator / denominator) * 100


# Logout user — POST-only to prevent CSRF. A plain <img src="/logout"> on a
# third-party page would otherwise log the user out of IRIS without consent
# (RFC 7231 §4.2.1: GET must be safe; CWE-650; SBA-ADV-20260128-03).
@dashboard_blueprint.route('/logout', methods=['POST'])
def logout():
    """
    Logout function. Erase its session and redirect to index i.e login
    :return: Page
    """
    if session['current_case']:
        current_user.ctx_case = session['current_case']['case_id']
        current_user.ctx_human_case = session['current_case']['case_name']
        db.session.commit()

    if is_authentication_oidc():
        if oidc_client.provider_info.get("end_session_endpoint"):
            try:
                logout_request = oidc_client.construct_EndSessionRequest(state=session["oidc_state"])
                logout_url = logout_request.request(oidc_client.provider_info["end_session_endpoint"])
                track_activity("user '{}' is being logged out".format(current_user.user), ctx_less=True, display_in_ui=False)
                logout_user()
                session.clear()
                return redirect(logout_url)
            except GrantError:
                track_activity(
                    f"no oidc session found for user '{current_user.user}', skipping oidc provider logout and continuing to logout local user",
                    ctx_less=True,
                    display_in_ui=False
                )
            except Exception as e:
                log.error(f"Error logging out: {e}")
                log.warning(f'Will continue to local logout')

    track_activity("user '{}' is being logged out".format(current_user.user), ctx_less=True, display_in_ui=False)

    logout_user()
    session.clear()

    return redirect(not_authenticated_redirection_url('/'))


@dashboard_blueprint.route('/dashboard/case_charts', methods=['GET'])
@ac_api_requires()
def get_cases_charts():
    """
    Get case charts
    :return: JSON
    """

    res = Cases.query.with_entities(
        Cases.open_date
    ).filter(
        Cases.open_date > (datetime.utcnow() - timedelta(days=365))
    ).order_by(
        Cases.open_date
    ).all()
    retr = [[], []]
    rk = {}
    for case in res:
        month = "{}/{}/{}".format(case.open_date.day, case.open_date.month, case.open_date.year)

        if month in rk:
            rk[month] += 1
        else:
            rk[month] = 1

        retr = [list(rk.keys()), list(rk.values())]

    return response_success("", retr)


@dashboard_blueprint.route('/dashboard/kpis', methods=['GET'])
@ac_api_requires()
def get_dashboard_kpis():
    try:
        start_dt, end_dt = _resolve_timeframe(request.args)
    except ValueError as exc:
        return response_error(str(exc))

    client_id = request.args.get('client_id', type=int)
    severity_filter = request.args.get('severity_id', type=int)
    case_status_filter = request.args.get('case_status_id', type=int)

    # Alert metrics ---------------------------------------------------
    alert_filters = []
    if client_id:
        alert_filters.append(Alert.alert_customer_id == client_id)
    if severity_filter:
        alert_filters.append(Alert.alert_severity_id == severity_filter)

    alert_query = Alert.query.filter(and_(Alert.alert_creation_time >= start_dt, Alert.alert_creation_time <= end_dt))
    if alert_filters:
        alert_query = alert_query.filter(*alert_filters)

    alert_rows = alert_query.with_entities(
        Alert.alert_id,
        Alert.alert_source_event_time,
        Alert.alert_creation_time,
        Alert.alert_resolution_status_id,
        Alert.alert_status_id
    ).all()

    total_alerts = len(alert_rows)

    false_positive_resolution = AlertResolutionStatus.query.with_entities(AlertResolutionStatus.resolution_status_id).filter(
        func.lower(AlertResolutionStatus.resolution_status_name) == 'false positive'
    ).first()
    false_positive_resolution_id = false_positive_resolution.resolution_status_id if false_positive_resolution else None

    escalated_status = AlertStatus.query.with_entities(AlertStatus.status_id).filter(
        func.lower(AlertStatus.status_name) == 'escalated'
    ).first()
    escalated_status_id = escalated_status.status_id if escalated_status else None

    alert_mttd_deltas = []
    false_positive_alerts = 0
    escalated_alerts = 0

    for row in alert_rows:
        source_time = _safe_datetime(row.alert_source_event_time)
        creation_time = _safe_datetime(row.alert_creation_time)

        if source_time and creation_time and creation_time >= source_time:
            alert_mttd_deltas.append(creation_time - source_time)

        if false_positive_resolution_id and row.alert_resolution_status_id == false_positive_resolution_id:
            false_positive_alerts += 1

        if escalated_status_id and row.alert_status_id == escalated_status_id:
            escalated_alerts += 1

    alerts_with_case_query = db.session.query(func.count(distinct(AlertCaseAssociation.alert_id))).join(
        Alert, Alert.alert_id == AlertCaseAssociation.alert_id
    ).filter(and_(Alert.alert_creation_time >= start_dt, Alert.alert_creation_time <= end_dt))

    if client_id:
        alerts_with_case_query = alerts_with_case_query.filter(Alert.alert_customer_id == client_id)
    if severity_filter:
        alerts_with_case_query = alerts_with_case_query.filter(Alert.alert_severity_id == severity_filter)

    alerts_with_cases = alerts_with_case_query.scalar() or 0

    mean_time_to_detect_seconds = _average_seconds(alert_mttd_deltas)
    detection_coverage_percent = _percentage(alerts_with_cases, total_alerts)
    incident_escalation_rate_percent = _percentage(escalated_alerts, total_alerts)

    # Case metrics ----------------------------------------------------
    case_filters = []
    if client_id:
        case_filters.append(Cases.client_id == client_id)
    if severity_filter:
        case_filters.append(Cases.severity_id == severity_filter)
    if case_status_filter is not None:
        case_filters.append(Cases.status_id == case_status_filter)

    cases_detected_query = Cases.query.filter(and_(Cases.initial_date >= start_dt, Cases.initial_date <= end_dt))
    if case_filters:
        cases_detected_query = cases_detected_query.filter(*case_filters)
    incidents_detected = cases_detected_query.count()

    cases_resolved_query = Cases.query.filter(Cases.close_date.isnot(None))
    if case_filters:
        cases_resolved_query = cases_resolved_query.filter(*case_filters)
    cases_resolved_query = cases_resolved_query.filter(Cases.close_date >= start_dt.date(), Cases.close_date <= end_dt.date())
    incidents_resolved = cases_resolved_query.count()

    false_positive_cases_query = Cases.query.filter(
        Cases.status_id == CaseStatus.false_positive.value,
        Cases.initial_date >= start_dt,
        Cases.initial_date <= end_dt
    )
    if case_filters:
        false_positive_cases_query = false_positive_cases_query.filter(*case_filters)
    false_positive_cases = false_positive_cases_query.count()

    cases_for_mttr_query = Cases.query.with_entities(Cases.initial_date, Cases.close_date)
    if case_filters:
        cases_for_mttr_query = cases_for_mttr_query.filter(*case_filters)
    cases_for_mttr_query = cases_for_mttr_query.filter(
        Cases.close_date.isnot(None),
        Cases.close_date >= start_dt.date(),
        Cases.close_date <= end_dt.date()
    )

    mttr_deltas = []
    for initial_date, close_date in cases_for_mttr_query:
        start_time = _safe_datetime(initial_date)
        if not start_time or not close_date:
            continue
        close_dt = datetime.combine(close_date, datetime.min.time())
        close_time = _safe_datetime(close_dt)
        if close_time and close_time >= start_time:
            mttr_deltas.append(close_time - start_time)

    cases_for_phase_query = Cases.query
    if case_filters:
        cases_for_phase_query = cases_for_phase_query.filter(*case_filters)
    cases_for_phase_query = cases_for_phase_query.filter(and_(Cases.initial_date >= start_dt, Cases.initial_date <= end_dt))
    cases_for_phase = cases_for_phase_query.all()

    mttc_deltas = []
    mttrv_deltas = []

    for case_obj in cases_for_phase:
        start_time = _safe_datetime(case_obj.initial_date)
        if not start_time:
            continue

        contain_time = _get_case_phase_timestamp(case_obj, ['contain'], ['containment_time', 'contained_at'])
        if contain_time and contain_time >= start_time:
            mttc_deltas.append(contain_time - start_time)

        recover_time = _get_case_phase_timestamp(case_obj, ['recover'], ['recovery_time', 'recovered_at'])
        if recover_time and recover_time >= start_time:
            mttrv_deltas.append(recover_time - start_time)

    mean_time_to_respond_seconds = _average_seconds(mttr_deltas)
    mean_time_to_contain_seconds = _average_seconds(mttc_deltas)
    mean_time_to_recover_seconds = _average_seconds(mttrv_deltas)

    false_positive_rate_percent = _percentage(false_positive_cases, incidents_detected)

    severity_query = db.session.query(Severity.severity_name, func.count(Cases.case_id)).join(
        Cases, Cases.severity_id == Severity.severity_id
    )
    severity_query = severity_query.filter(and_(Cases.initial_date >= start_dt, Cases.initial_date <= end_dt))
    if case_filters:
        severity_query = severity_query.filter(*case_filters)
    severity_query = severity_query.group_by(Severity.severity_name)
    severity_counts = severity_query.all()

    unspecified_severity_count_query = Cases.query.filter(
        Cases.severity_id.is_(None),
        Cases.initial_date >= start_dt,
        Cases.initial_date <= end_dt
    )
    if case_filters:
        unspecified_severity_count_query = unspecified_severity_count_query.filter(*case_filters)
    unspecified_severity_count = unspecified_severity_count_query.count()

    severity_distribution = []
    denominator = incidents_detected if incidents_detected else None

    for severity_name, count in severity_counts:
        percent = _percentage(count, denominator) if denominator else None
        severity_distribution.append({
            'severity': severity_name or 'Unspecified',
            'count': count,
            'percentage': percent
        })

    if unspecified_severity_count:
        percent = _percentage(unspecified_severity_count, denominator) if denominator else None
        severity_distribution.append({
            'severity': 'Unspecified',
            'count': unspecified_severity_count,
            'percentage': percent
        })

    response_data = {
        'timeframe': {
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat()
        },
        'filters': {
            'client_id': client_id,
            'severity_id': severity_filter,
            'case_status_id': case_status_filter
        },
        'alerts': {
            'total': total_alerts,
            'false_positive_count': false_positive_alerts,
            'associated_with_cases': alerts_with_cases
        },
        'metrics': {
            'mean_time_to_detect': _duration_payload(mean_time_to_detect_seconds),
            'mean_time_to_respond': _duration_payload(mean_time_to_respond_seconds),
            'incidents_detected': incidents_detected,
            'incidents_resolved': incidents_resolved,
            'false_positive_incidents': false_positive_cases,
            'false_positive_rate_percent': false_positive_rate_percent,
            'detection_coverage_percent': detection_coverage_percent,
            'incident_escalation_rate_percent': incident_escalation_rate_percent,
            'severity_distribution': severity_distribution
        }
    }

    return response_success('', data=response_data)


@dashboard_blueprint.route('/')
def root():
    if app.config['DEMO_MODE_ENABLED'] == 'True':
        return redirect(url_for('demo-landing.demo_landing'))

    return redirect(url_for('index.index'))


@dashboard_blueprint.route('/dashboard')
@ac_requires()
def index(caseid, url_redir):
    """
    Index page. Load the dashboard data, create the add customer form
    :return: Page
    """
    if url_redir:
        return redirect(url_for('index.index', cid=caseid if caseid is not None else 1, redirect=True))

    msg = None

    acgucc = ac_get_user_case_counts(current_user.id)

    status_names = ['New', 'Pending', 'In progress']
    status_rows = AlertStatus.query.with_entities(AlertStatus.status_id).filter(
        AlertStatus.status_name.in_(status_names)
    ).all()
    status_ids = [row.status_id for row in status_rows]

    assigned_alerts_count = 0
    if status_ids:
        assigned_alerts_count = Alert.query.filter(
            Alert.alert_owner_id == current_user.id,
            Alert.alert_status_id.in_(status_ids)
        ).count()

    alerts_filter_params = {'alert_owner_id': current_user.id}
    if caseid is not None:
        alerts_filter_params['cid'] = caseid
    if status_ids:
        alerts_filter_params['custom_conditions'] = json.dumps([
            {
                'field': 'alert_status_id',
                'operator': 'in',
                'value': status_ids
            }
        ], separators=(',', ':'))

    assigned_alerts_link = url_for('alerts.alerts_list_view_route')
    if alerts_filter_params:
        assigned_alerts_link = f"{assigned_alerts_link}?{urlencode(alerts_filter_params)}"

    data = {
        "user_open_count": acgucc[2],
        "cases_open_count": acgucc[1],
        "cases_count": acgucc[0],
        "assigned_alerts_count": assigned_alerts_count,
        "assigned_alerts_link": assigned_alerts_link,
    }

    # Create the customer form to be able to quickly add a customer
    form = FlaskForm()

    return render_template('index.html', data=data, form=form, msg=msg)


@dashboard_blueprint.route('/global/tasks/list', methods=['GET'])
@ac_api_requires()
def get_gtasks():

    tasks_list = list_global_tasks()

    if tasks_list:
        output = [c._asdict() for c in tasks_list]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output
    }

    return response_success("", data=ret)


@dashboard_blueprint.route('/user/cases/list', methods=['GET'])
@ac_api_requires()
def list_own_cases():

    cases = list_user_cases(
        request.args.get('show_closed', 'false', type=str).lower() == 'true'
    )

    return response_success("", data=CaseDetailsSchema(many=True).dump(cases))


@dashboard_blueprint.route('/global/tasks/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def view_gtask(cur_id):

    task = get_global_task(task_id=cur_id)
    if not task:
        return response_error(f'Global task ID {cur_id} not found')

    return response_success("", data=task._asdict())


@dashboard_blueprint.route('/user/tasks/list', methods=['GET'])
@ac_api_requires()
def get_utasks():

    ct = list_user_tasks()

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output
    }

    return response_success("", data=ret)


@dashboard_blueprint.route('/user/reviews/list', methods=['GET'])
@ac_api_requires()
def get_reviews():

    ct = list_user_reviews()

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []


    return response_success("", data=output)


@dashboard_blueprint.route('/user/tasks/status/update', methods=['POST'])
@ac_api_requires()
@ac_requires_case_identifier()
def utask_statusupdate(caseid):
    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    case_id = jsdata.get('case_id') if jsdata.get('case_id') else caseid
    task_id = jsdata.get('task_id')
    task = CaseTasks.query.filter(CaseTasks.id == task_id, CaseTasks.task_case_id == case_id).first()
    if not task:
        return response_error(f"Invalid case task ID {task_id} for case {case_id}")

    status_id = jsdata.get('task_status_id')
    status = TaskStatus.query.filter(TaskStatus.id == status_id).first()
    if not status:
        return response_error(f"Invalid task status ID {status_id}")

    task.task_status_id = status_id
    try:

        db.session.commit()

    except Exception as e:
        return response_error(f"Unable to update task. Error {e}")

    task_schema = CaseTaskSchema()
    return response_success("Updated", data=task_schema.dump(task))


@dashboard_blueprint.route('/global/tasks/add/modal', methods=['GET'])
@ac_api_requires()
def add_gtask_modal():
    task = GlobalTasks()

    form = CaseGlobalTaskForm()

    form.task_assignee_id.choices = [(user.id, user.name) for user in User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    return render_template("modal_add_global_task.html", form=form, task=task, uid=current_user.id, user_name=None)


@dashboard_blueprint.route('/global/tasks/add', methods=['POST'])
@ac_api_requires()
@ac_requires_case_identifier()
def add_gtask(caseid):

    try:

        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_create', data=request.get_json(), caseid=caseid)

        gtask = gtask_schema.load(request_data)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    gtask.task_userid_update = current_user.id
    gtask.task_open_date = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()

    try:

        db.session.add(gtask)
        db.session.commit()

    except Exception as e:
        return response_error(msg="Data error", data=e.__str__())

    gtask = call_modules_hook('on_postload_global_task_create', data=gtask, caseid=caseid)
    track_activity("created new global task \'{}\'".format(gtask.task_title), caseid=caseid)

    return response_success('Task added', data=gtask_schema.dump(gtask))


@dashboard_blueprint.route('/global/tasks/update/<int:cur_id>/modal', methods=['GET'])
@ac_api_requires()
def edit_gtask_modal(cur_id):
    form = CaseGlobalTaskForm()
    task = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    # Render the task
    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()

    return render_template("modal_add_global_task.html", form=form, task=task,
                           uid=task.task_assignee_id, user_name=user_name)


@dashboard_blueprint.route('/global/tasks/update/<int:cur_id>', methods=['POST'])
@ac_api_requires()
@ac_requires_case_identifier()
def edit_gtask(cur_id, caseid):

    form = CaseGlobalTaskForm()
    task = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    form.task_assignee_id.choices = [(user.id, user.name) for user in User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    if not task:
        return response_error(msg="Data error", data="Invalid task ID")

    try:
        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_update', data=request.get_json(),
                                         caseid=caseid)

        gtask = gtask_schema.load(request_data, instance=task)
        gtask.task_userid_update = current_user.id
        gtask.task_last_update = datetime.utcnow()

        db.session.commit()

        gtask = call_modules_hook('on_postload_global_task_update', data=gtask, caseid=caseid)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    track_activity("updated global task {} (status {})".format(task.task_title, task.task_status_id), caseid=caseid)

    return response_success('Task updated', data=gtask_schema.dump(gtask))


@dashboard_blueprint.route('/global/tasks/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires()
@ac_requires_case_identifier()
def gtask_delete(cur_id, caseid):

    call_modules_hook('on_preload_global_task_delete', data=cur_id, caseid=caseid)

    if not cur_id:
        return response_error("Missing parameter")

    data = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    if not data:
        return response_error("Invalid global task ID")

    GlobalTasks.query.filter(GlobalTasks.id == cur_id).delete()
    db.session.commit()

    call_modules_hook('on_postload_global_task_delete', data=request.get_json(), caseid=caseid)
    track_activity("deleted global task ID {}".format(cur_id), caseid=caseid)

    return response_success("Task deleted")
