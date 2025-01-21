# IMPORTS ------------------------------------------------
import json
from flask import Blueprint, abort, jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from marshmallow import ValidationError

from app import db
from app.datamgmt.manage.manage_webhooks_db import get_webhooks_list
from app.datamgmt.manage.manage_webhooks_db import get_webhook_by_id
from app.datamgmt.manage.manage_webhooks_db import delete_webhook_by_id
from app.datamgmt.manage.manage_webhooks_db import validate_webhook
from app.forms import AddAssetForm, WebhookForm
from app.models import Webhook
from app.models.authorization import Permissions
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import WebhookSchema
from app.util import ac_api_requires
from app.util import ac_requires_case_identifier
from app.util import ac_requires
from app.util import response_error
from app.util import response_success
from app.datamgmt.manage.manage_case_templates_db import get_action_by_case_template_id_and_task_id

manage_webhooks_blueprint = Blueprint('manage_webhooks',
                                            __name__,
                                            template_folder='templates')


# CONTENT ------------------------------------------------
@manage_webhooks_blueprint.route('/manage/webhooks', methods=['GET'])
@ac_requires(Permissions.webhooks_read)
def manage_webhooks(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_webhooks.manage_webhooks', cid=caseid))

    form = AddAssetForm()

    return render_template('manage_webhooks.html', form=form)


@manage_webhooks_blueprint.route('/manage/webhooks/list', methods=['GET'])
@ac_api_requires()
def list_webhooks():
    """Show a list of webhooks

    Returns:
        Response: List of webhooks
    """
    case_id = request.args.get("cid")  # Use 'cid' since it's coming from query parameters
    webhooks = get_webhooks_list()

    # Return the attributes
    return response_success("", data=webhooks)

@manage_webhooks_blueprint.route('/manage/webhooks/listbyCasetemplateId/<int:cur_id>/<int:task_id>', methods=['GET'])
@ac_api_requires()
def list_webhooks_by_case_template_id(cur_id, task_id):
    """Show a list of webhooks by case template id

    Returns:
        Response: List of webhooks by case template id
    """

    caseid = request.args.get('cid')
    webhooks = get_action_by_case_template_id_and_task_id(cur_id, task_id, caseid)

    # Return the attributes
    return response_success("",data = webhooks)

@manage_webhooks_blueprint.route('/manage/webhooks/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.webhooks_read)
def get_webhook(cur_id):
    """Fetch a webhook by ID

    Args:
        cur_id (int): webhook ID

    Returns:
        JSON Response: Webhook details
    """
    webhook = get_webhook_by_id(cur_id)
    if not webhook:
        return response_error(f"Invalid webhook ID {cur_id}")

    try:
        webhook_data = WebhookSchema().dump(webhook)
    except ValidationError as error:
        return response_error("Could not serialize webhook", data=str(error))

    return response_success("Webhook retrieved successfully", data=webhook_data)



@manage_webhooks_blueprint.route('/manage/webhooks/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.webhooks_read)
def webhook_modal(cur_id, caseid, url_redir):
    """Get an webhook

    Args:
        cur_id (int): webhook id

    Returns:
        HTML Template: webhook modal
    """
    if url_redir:
        return redirect(url_for('manage_webhooks.manage_webhooks', cid=caseid))

    form = WebhookForm()

    webhook = get_webhook_by_id(cur_id)
    if not webhook:
        return response_error(f"Invalid webhook ID {cur_id}")

    # Temporary : for now we build the full JSON form object based on case templates attributes
    # Next step : add more fields to the form
    webhook_dict = {
        "name": webhook.name,
        "header_auth": webhook.header_auth,
        "payload_schema": webhook.payload_schema,
        "url": webhook.url
    }

    form.webhook_json.data = webhook_dict

    return render_template("modal_webhook.html", form=form, webhook=webhook)


@manage_webhooks_blueprint.route('/manage/webhooks/add/modal', methods=['GET'])
@ac_api_requires(Permissions.webhooks_write)
def add_template_modal():
    webhook = Webhook()
    form = WebhookForm()
    form.webhook_json.data = {
        "name": "webhook name",
        "header_auth": [
            {
                "key": "key 1",
                "value": "value 1"
            }
        ],
        "payload_schema": {
        "type": "Webhook Payload Type",
        "description": "Webhook payload Description",
        "minItems": 1,
        "uniqueItems": "true",
        "items": {
            "type": "object",
            "required": [
                "property"
            ],
            "properties": {
                "property 1": {
                    "type": "property type",
                    "minLength": 1
                },
                "property 2": {
                    "type": "object",
                    "properties": {
                        "sub property 1": {
                            "type": "property type",
                            "minLength": 1
                        }
                    }
                }
            }
        }
    },
    "url": "http://webhookexampleurl.com"
    }

    return render_template("modal_webhook.html", form=form, webhook=webhook)



@manage_webhooks_blueprint.route('/manage/webhooks/upload/modal', methods=['GET'])
@ac_api_requires(Permissions.webhooks_write)
def upload_template_modal():
    return render_template("modal_upload_webhook.html")


@manage_webhooks_blueprint.route('/manage/webhooks/add', methods=['POST'])
@ac_api_requires(Permissions.webhooks_write)
@ac_requires_case_identifier()
def add_webhook(caseid):
    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    webhook_json = data.get('webhook_json')
    if not webhook_json:
        return response_error("Invalid request")

    try:
        webhook_dict = json.loads(webhook_json)
    except Exception as e:
        return response_error("Invalid JSON", data=str(e))

    try:
        logs = validate_webhook(webhook_dict, update=False)
        if logs is not None:
            return response_error("Found errors in webhooks", data=logs)
    except Exception as e:
        return response_error("Found errors in webhooks", data=str(e))

    try:
        webhook_dict["created_by_user_id"] = current_user.id
        webhook_data = WebhookSchema().load(webhook_dict)
        webhook = Webhook(**webhook_data)
        db.session.add(webhook)
        db.session.commit()
    except Exception as e:
        return response_error("Could not add webhook into DB", data=str(e))

    track_activity(f"webhook '{webhook.name}' added", caseid=caseid, ctx_less=True)

    return response_success("Added successfully", data=WebhookSchema().dump(webhook))


@manage_webhooks_blueprint.route('/manage/webhooks/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.webhooks_write)
def update_webhook(cur_id):
    if not request.is_json:
        return response_error("Invalid request")

    webhook = get_webhook_by_id(cur_id)
    if not webhook:
        return response_error(f"Invalid webhook ID {cur_id}")

    data = request.get_json()
    updated_webhook_json = data.get('webhook_json')
    if not updated_webhook_json:
        return response_error("Invalid request")

    try:
        updated_webhook_dict = json.loads(updated_webhook_json)
    except Exception as e:
        return response_error("Invalid JSON", data=str(e))

    try:
        logs = validate_webhook(updated_webhook_dict, update=True)
        if logs is not None:
            return response_error("Found errors in webhook", data=logs)
    except Exception as e:
        return response_error("Found errors in webhook", data=str(e))

    webhook_schema = WebhookSchema()

    try:
        # validate the request data and load it into an instance of the `Webhook` object
        webhook_data = webhook_schema.load(updated_webhook_dict, partial=True)
        # update the existing `webhook` object with the new data
        webhook.update_from_dict(webhook_data)
        # commit the changes to the database
        db.session.commit()
    except ValidationError as error:
        return response_error("Could not validate webhook", data=str(error))

    return response_success("webhook updated")


@manage_webhooks_blueprint.route('/manage/webhooks/delete/<int:webhook_id>', methods=['POST'])
@ac_api_requires(Permissions.webhooks_write)
@ac_requires_case_identifier()
def delete_webhook(webhook_id, caseid):
    webhook = get_webhook_by_id(webhook_id)
    if webhook is None:
        return response_error('webhook not found')

    webhook_name = webhook.name

    delete_webhook_by_id(webhook_id)
    db.session.commit()

    track_activity(f"webhook '{webhook_name}' deleted", caseid=caseid, ctx_less=True)
    return response_success("Deleted successfully")

