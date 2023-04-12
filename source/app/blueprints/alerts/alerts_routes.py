#!/usr/bin/env python3
#
#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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
from flask_wtf import FlaskForm
from typing import Union, List

from datetime import datetime

from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import current_user
from werkzeug import Response

import app
from app import db
from app.datamgmt.alerts.alerts_db import get_filtered_alerts, get_alert_by_id, create_case_from_alert, \
    merge_alert_in_case, unmerge_alert_from_case, cache_similar_alert, get_related_alerts, get_related_alerts_details, \
    get_alert_comments, delete_alert_comment, get_alert_comment
from app.datamgmt.case.case_db import get_case
from app.iris_engine.access_control.utils import ac_set_new_case_access
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.alerts import AlertStatus
from app.models.authorization import Permissions
from app.schema.marshables import AlertSchema, CaseSchema, CommentSchema
from app.util import ac_api_requires, response_error, str_to_bool, add_obj_history_entry, ac_requires
from app.util import response_success

alerts_blueprint = Blueprint(
    'alerts',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@alerts_blueprint.route('/alerts/filter', methods=['GET'])
@ac_api_requires(Permissions.alerts_read, no_cid_required=True)
def alerts_list_route(caseid) -> Response:
    """
    Get a list of alerts from the database

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    alert_schema = AlertSchema()

    filtered_data = get_filtered_alerts(
        start_date=request.args.get('source_start_date'),
        end_date=request.args.get('source_end_date'),
        title=request.args.get('alert_title'),
        description=request.args.get('alert_description'),
        status=request.args.get('alert_status_id', type=int),
        severity=request.args.get('alert_severity_id', type=int),
        owner=request.args.get('alert_owner_id', type=int),
        source=request.args.get('alert_source'),
        tags=request.args.get('alert_tags'),
        classification=request.args.get('alert_classification_id', type=int),
        client=request.args.get('alert_customer_id'),
        case_id=request.args.get('case_id', type=int),
        alert_id=request.args.get('alert_id', type=int),
        page=page,
        per_page=per_page,
        sort=request.args.get('sort')
    )

    if filtered_data is None:
        return response_error('Filtering error')

    alerts = {
        'total': filtered_data.total,
        'alerts': alert_schema.dump(filtered_data.items, many=True),
        'last_page': filtered_data.pages,
        'current_page': filtered_data.page,
        'next_page': filtered_data.next_num if filtered_data.has_next else None,
    }

    return response_success(data=alerts)


@alerts_blueprint.route('/alerts/add', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_add_route(caseid) -> Response:
    """
    Add a new alert to the database

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """

    if not request.json:
        return response_error('No JSON data provided')

    alert_schema = AlertSchema()

    try:
        # Load the JSON data from the request
        data = request.get_json()

        # Deserialize the JSON data into an Alert object
        new_alert = alert_schema.load(data)

        new_alert.alert_creation_time = datetime.utcnow()

        # Add the new alert to the session and commit it
        db.session.add(new_alert)
        db.session.commit()

        # Add history entry
        add_obj_history_entry(new_alert, 'Alert created')

        # Cache the alert for similarities check
        cache_similar_alert(new_alert.alert_customer_id, assets=data.get('alert_assets'),
                            iocs=data.get('alert_iocs'), alert_id=new_alert.alert_id)

        # Return the newly created alert as JSON
        return response_success(data=alert_schema.dump(new_alert))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/<int:alert_id>', methods=['GET'])
@ac_api_requires(Permissions.alerts_read, no_cid_required=True)
def alerts_get_route(caseid, alert_id) -> Response:
    """
    Get an alert from the database

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """

    alert_schema = AlertSchema()

    # Get the alert from the database
    alert = get_alert_by_id(alert_id)

    # Return the alert as JSON
    if alert is None:
        return response_error('Alert not found')

    alert_dump = alert_schema.dump(alert)

    # Get similar alerts
    similar_alerts = get_related_alerts(alert.alert_customer_id, alert.alert_assets, alert.alert_iocs)
    alert_dump['related_alerts'] = similar_alerts

    return response_success(data=alert_dump)


@alerts_blueprint.route('/alerts/similarities/<int:alert_id>', methods=['GET'])
@ac_api_requires(Permissions.alerts_read, no_cid_required=True)
def alerts_similarities_route(caseid, alert_id) -> Response:
    """
    Get an alert and similarities from the database

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """

    # Get the alert from the database
    alert = get_alert_by_id(alert_id)

    # Return the alert as JSON
    if alert is None:
        return response_error('Alert not found')

    # Get similar alerts
    similar_alerts = get_related_alerts_details(alert.alert_customer_id, alert.alert_assets, alert.alert_iocs)

    return response_success(data=similar_alerts)


@alerts_blueprint.route('/alerts/update/<int:alert_id>', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_update_route(alert_id, caseid) -> Response:
    """
    Update an alert in the database

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """
    if not request.json:
        return response_error('No JSON data provided')

    alert = get_alert_by_id(alert_id)
    if not alert:
        return response_error('Alert not found')

    alert_schema = AlertSchema()

    try:
        # Load the JSON data from the request
        data = request.get_json()

        # Deserialize the JSON data into an Alert object
        updated_alert = alert_schema.load(data, instance=alert, partial=True)

        # Save the changes
        db.session.commit()

        # Return the updated alert as JSON
        return response_success(data=alert_schema.dump(updated_alert))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/batch/update', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_batch_update_route(caseid: int) -> Response:
    """
    Update multiple alerts in the database

    args:
        caseid (int): The case id

    returns:
        Response: The response
    """
    if not request.json:
        return response_error('No JSON data provided')

    # Load the JSON data from the request
    data = request.get_json()

    # Get the list of alert IDs and updates from the request data
    alert_ids: List[int] = data.get('alert_ids', [])
    updates = data.get('updates', {})

    if not alert_ids:
        return response_error('No alert IDs provided')

    alert_schema = AlertSchema()

    # Process each alert ID
    for alert_id in alert_ids:
        alert = get_alert_by_id(alert_id)
        if not alert:
            return response_error(f'Alert with ID {alert_id} not found')

        try:
            # Deserialize the JSON data into an Alert object
            updated_alert = alert_schema.load(updates, instance=alert, partial=True)

            # Save the changes
            db.session.commit()

        except Exception as e:
            # Handle any errors during deserialization or DB operations
            return response_error(str(e))

    # Return a success response
    return response_success(msg='Batch update successful')


@alerts_blueprint.route('/alerts/delete/<int:alert_id>', methods=['POST'])
@ac_api_requires(Permissions.alerts_delete, no_cid_required=True)
def alerts_delete_route(alert_id, caseid) -> Response:
    """
    Delete an alert from the database

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """

    alert = get_alert_by_id(alert_id)
    if not alert:
        return response_error('Alert not found')

    try:
        # Delete the alert from the database
        db.session.delete(alert)
        db.session.commit()

        # Return the deleted alert as JSON
        return response_success(data={'alert_id': alert_id})

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/escalate/<int:alert_id>', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_escalate_route(alert_id, caseid) -> Response:
    """
    Escalate an alert

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """

    alert = get_alert_by_id(alert_id)
    if not alert:
        return response_error('Alert not found')

    if request.json is None:
        return response_error('No JSON data provided')

    data = request.get_json()

    iocs_import_list: List[str] = data.get('iocs_import_list')
    assets_import_list: List[str] = data.get('assets_import_list')
    note: str = data.get('note')
    import_as_event: bool = data.get('import_as_event')
    case_tags:str = data.get('case_tags')

    try:
        # Escalate the alert to a case
        alert.alert_status_id = AlertStatus.query.filter_by(status_name='Escalated').first().status_id
        db.session.commit()

        # Create a new case from the alert
        case = create_case_from_alert(alert, iocs_list=iocs_import_list, assets_list=assets_import_list, note=note,
                                      import_as_event=import_as_event, case_tags=case_tags)

        if not case:
            return response_error('Failed to create case from alert')

        ac_set_new_case_access(None, case.case_id)

        case = call_modules_hook('on_postload_case_create', data=case, caseid=caseid)

        add_obj_history_entry(case, 'created')
        track_activity("new case {case_name} created from alert".format(case_name=case.name),
                       caseid=caseid, ctx_less=True)

        # Return the updated alert as JSON
        return response_success(data=CaseSchema().dump(case))

    except Exception as e:

        app.logger.exception(e)

        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/merge/<int:alert_id>', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_merge_route(alert_id, caseid) -> Response:
    """
    Merge an alert into a case

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """
    if request.json is None:
        return response_error('No JSON data provided')

    data = request.get_json()

    target_case_id = data.get('target_case_id')
    if target_case_id is None:
        return response_error('No target case id provided')

    alert = get_alert_by_id(alert_id)
    if not alert:
        return response_error('Alert not found')

    case = get_case(target_case_id)
    if not case:
        return response_error('Target case not found')

    iocs_import_list: List[str] = data.get('iocs_import_list')
    assets_import_list: List[str] = data.get('assets_import_list')
    note: str = data.get('note')
    import_as_event: bool = data.get('import_as_event')
    case_tags = data.get('case_tags')

    try:
        # Merge the alert into a case
        alert.alert_status_id = AlertStatus.query.filter_by(status_name='Merged').first().status_id
        db.session.commit()

        # Merge alert in the case
        merge_alert_in_case(alert, case, iocs_list=iocs_import_list, assets_list=assets_import_list, note=note,
                            import_as_event=import_as_event, case_tags=case_tags)

        # Return the updated alert as JSON
        return response_success(data=CaseSchema().dump(case))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/unmerge/<int:alert_id>', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alerts_unmerge_route(alert_id, caseid) -> Response:
    """
    Unmerge an alert from a case

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """
    if request.json is None:
        return response_error('No JSON data provided')

    target_case_id = request.json.get('target_case_id')
    if target_case_id is None:
        return response_error('No target case id provided')

    alert = get_alert_by_id(alert_id)
    if not alert:
        return response_error('Alert not found')

    case = get_case(target_case_id)
    if not case:
        return response_error('Target case not found')

    try:
        # Unmerge alert from the case
        unmerge_alert_from_case(alert, case)

        # Return the updated alert as JSON
        return response_success(data=CaseSchema().dump(case))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts', methods=['GET'])
@ac_requires(Permissions.alerts_read, no_cid_required=True)
def alerts_list_view_route(caseid, url_redir) -> Union[str, Response]:
    """
    List all alerts

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """
    if url_redir:
        return redirect(url_for('alerts.alerts_list_view_route', cid=caseid))

    form = FlaskForm()

    return render_template('alerts.html', caseid=caseid, form=form)


@alerts_blueprint.route('/alerts/<int:cur_id>/comments/modal', methods=['GET'])
@ac_requires(Permissions.alerts_read, no_cid_required=True)
def alert_comment_modal(cur_id, caseid, url_redir):
    """
    Get the modal for the alert comments

    args:
        cur_id (int): The alert id
        caseid (str): The case id

    returns:
        Response: The response
    """
    if url_redir:
        return redirect(url_for('alerts.alerts_list_view_route', cid=caseid, redirect=True))

    alert = get_alert_by_id(cur_id)
    if not alert:
        return response_error('Invalid alert ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='alerts',
                           title=alert.alert_id)


@alerts_blueprint.route('/alerts/<int:alert_id>/comments/list', methods=['GET'])
@ac_api_requires(Permissions.alerts_read, no_cid_required=True)
def alert_comments_get(alert_id, caseid):
    """
    Get the comments for an alert

    args:
        alert_id (int): The alert id
        caseid (str): The case id

    returns:
        Response: The response
    """

    alert_comments = get_alert_comments(alert_id)
    if alert_comments is None:
        return response_error('Invalid alert ID')

    return response_success(data=CommentSchema(many=True).dump(alert_comments))


@alerts_blueprint.route('/alerts/<int:alert_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_requires(Permissions.alerts_write, no_cid_required=True)
def alert_comment_delete(alert_id, com_id, caseid):
    """
    Delete a comment for an alert

    args:
        alert_id (int): The alert id
        com_id (int): The comment id
        caseid (str): The case id

    returns:
        Response: The response
    """

    success, msg = delete_alert_comment(alert_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_alert_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on alert {alert_id} deleted", caseid=caseid)
    return response_success(msg)


@alerts_blueprint.route('/case/timeline/events/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_requires(Permissions.alerts_read, no_cid_required=True)
def case_comment_get(cur_id, com_id, caseid):
    """
    Get a comment for an alert

    args:
        cur_id (int): The alert id
        com_id (int): The comment id
        caseid (str): The case id

    returns:
        Response: The response
    """

    comment = get_alert_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=CommentSchema().dump(comment))

#
# @alerts_blueprint.route('/case/timeline/events/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
# @ac_api_requires(Permissions.alerts_write, no_cid_required=True)
# def case_comment_edit(cur_id, com_id, caseid):
#
#     return case_comment_update(com_id, 'events', caseid)
#
#
# @alerts_blueprint.route('/case/timeline/events/<int:cur_id>/comments/add', methods=['POST'])
# @ac_api_requires(Permissions.alerts_write, no_cid_required=True)
# def case_comment_add(cur_id, caseid):
#
#     try:
#         event = get_case_event(event_id=cur_id, caseid=caseid)
#         if not event:
#             return response_error('Invalid event ID')
#
#         comment_schema = CommentSchema()
#
#         comment = comment_schema.load(request.get_json())
#         comment.comment_case_id = caseid
#         comment.comment_user_id = current_user.id
#         comment.comment_date = datetime.now()
#         comment.comment_update_date = datetime.now()
#         db.session.add(comment)
#         db.session.commit()
#
#         add_comment_to_event(event.event_id, comment.comment_id)
#
#         add_obj_history_entry(event, 'commented')
#
#         db.session.commit()
#
#         hook_data = {
#             "comment": comment_schema.dump(comment),
#             "event": EventSchema().dump(event)
#         }
#         call_modules_hook('on_postload_event_commented', data=hook_data, caseid=caseid)
#
#         track_activity(f"event \"{event.event_title}\" commented", caseid=caseid)
#         return response_success("Event commented", data=comment_schema.dump(comment))
#
#     except marshmallow.exceptions.ValidationError as e:
#         return response_error(msg="Data error", data=e.normalized_messages(), status=400)
#
