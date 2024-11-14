#  IRIS Source Code
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
import marshmallow
from datetime import datetime
from typing import List, Optional, Union

from app import db
from app.datamgmt.case.case_notes_db import add_note
from app.datamgmt.case.case_tasks_db import add_task
from app.datamgmt.manage.manage_case_classifications_db import get_case_classification_by_name
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.models import CaseTemplate, Webhook, Cases, Tags, NoteDirectory
from app.models.authorization import User
from app.schema.marshables import CaseSchema, CaseTaskSchema, CaseNoteDirectorySchema, CaseNoteSchema


def get_webhooks_list() -> List[dict]:
    """Get a list of webhooks

    Returns:
        List[dict]: List of webhooks
    """
    webhooks = Webhook.query.with_entities(
        Webhook.id,
        Webhook.name,
        Webhook.header_auth,
        Webhook.payload_schema,
        Webhook.url,
        Webhook.created_at,
        Webhook.updated_at,
        User.name.label('added_by')
    ).join(
        Webhook.created_by_user
    ).all()

    c_cl = [row._asdict() for row in webhooks]
    return c_cl


def get_webhook_by_id(cur_id: int) -> Webhook:
    """Get a webhook

    Args:
        cur_id (int): webhook id

    Returns:
        Webhook: Webhook
    """
    webhook = Webhook.query.filter_by(id=cur_id).first()
    return webhook


def delete_webhook_by_id(webhook_id: int):
    """Delete a webhook

    Args:
        webhook_id (int): webhook id
    """
    Webhook.query.filter_by(id=webhook_id).delete()


def validate_webhook(data: dict, update: bool = False) -> Optional[str]:
    try:
        if not update:
            # If it's not an update, we check the required fields
            if "name" not in data:
                return "Name is required."

            # if "display_name" not in data or not data["display_name"].strip():
            #     data["display_name"] = data["name"]
        # We check that name is not empty
        if "name" in data and not data["name"].strip():
            return "Name cannot be empty."

        # # We check that author length is not above 128 chars
        # if "author" in data and len(data["author"]) > 128:
        #     return "Author cannot be longer than 128 characters."

        # # We check that author length is not above 128 chars
        # if "author" in data and len(data["author"]) > 128:
        #     return "Author cannot be longer than 128 characters."

        # # We check that prefix length is not above 32 chars
        # if "title_prefix" in data and len(data["title_prefix"]) > 32:
        #     return "Prefix cannot be longer than 32 characters."

        # # We check that tags, if any, are a list of strings
        # if "tags" in data:
        #     if not isinstance(data["tags"], list):
        #         return "Tags must be a list."
        #     for tag in data["tags"]:
        #         if not isinstance(tag, str):
        #             return "Each tag must be a string."

        

        # We check that tasks, if any, are a list of dictionaries with mandatory keys
        if "header_auth" in data:
            if not isinstance(data["header_auth"], list):
                return "Header Auth must be a list."
            for auth in data["header_auth"]:
                if not isinstance(auth, dict):
                    return "Each header auth must be a dictionary."
                if "key" not in auth:
                    return "Each auth must have a 'key' field."
                # if "tags" in task:
                #     if not isinstance(task["tags"], list):
                #         return "Task tags must be a list."
                #     for tag in task["tags"]:
                #         if not isinstance(tag, str):
                #             return "Each tag must be a string."

        # We check that note groups, if any, are a list of dictionaries with mandatory keys
        if "note_groups" in data:
            return "Note groups has been replaced by note_directories."

        if "payload_schema" in data:
            if not isinstance(data["payload_schema"], list):
                return "Payload Schema must be a list."
            for payload in data["payload_schema"]:
                if not isinstance(payload, dict):
                    return "Each payload schema must be a dictionary."
                if "type" not in payload:
                    return "Each payload directory must have a 'type' field."
                if "properties" in payload:
                    if not isinstance(payload["properties"], list):
                        return "Properties must be a list."
                    for property in payload["properties"]:
                        if not isinstance(property, dict):
                            return "Each property must be a dictionary."
                        if "type" not in property:
                            return "Each property must have a 'type' field."

        # If all checks succeeded, we return None to indicate everything is has been validated
        return None
    except Exception as e:
        return str(e)


def webhook_pre_modifier(case_schema: CaseSchema, case_template_id: str):
    webhook = get_webhook_by_id(int(case_template_id))
    if not webhook:
        return None
    if webhook.title_prefix:
        case_schema.name = webhook.title_prefix + " " + case_schema.name[0]

    case_classification = get_case_classification_by_name(webhook.classification)
    if case_classification:
        case_schema.classification_id = case_classification.id

    return case_schema


def webhook_populate_header_auth(case: Cases, webhook: Webhook):
    logs = []
    # Update webhooks
    for header_auth_hook in webhook.header_auth:
        try:
            # validate before saving
            auth_schema = CaseTaskSchema()

            # Remap case task template fields
            # Set status to "To Do" which is ID 1
            mapped_header_auth_hook = {
                "header_auth_key": header_auth_hook['key'],
                "task_status_id": 1
            }

            mapped_header_auth_hook = call_modules_hook('on_preload_task_create', data=mapped_header_auth_hook, caseid=case.case_id)

            task = auth_schema.load(mapped_header_auth_hook)

            assignee_id_list = []

            ctask = add_task(task=task,
                             assignee_id_list=assignee_id_list,
                             user_id=case.user_id,
                             caseid=case.case_id
                             )

            ctask = call_modules_hook('on_postload_task_create', data=ctask, caseid=case.case_id)

            if not ctask:
                logs.append("Unable to create auth for internal reasons")

        except marshmallow.exceptions.ValidationError as e:
            logs.append(e.messages)

    return logs


def webhook_populate_properties(case: Cases, payload_schema_hook: dict, ng: NoteDirectory):
    logs = []
    if payload_schema_hook.get("properties"):
        for property_schema in payload_schema_hook["properties"]:
            # validate before saving
            property_sch = CaseNoteSchema()

            mapped_property_schema = {
                "directory_id": ng.id,
                "property_property": property_schema["property"],
                "property_type": property_schema["type"] if property_schema.get("type") else ""
            }

            mapped_property_schema = call_modules_hook('on_preload_note_create',
                                                     data=mapped_property_schema,
                                                     caseid=case.case_id)

            property_sch.verify_directory_id(mapped_property_schema, caseid=ng.case_id)
            note = property_sch.load(mapped_property_schema)

            note.note_creationdate = datetime.utcnow()
            note.note_lastupdate = datetime.utcnow()
            note.note_user = case.user_id
            note.note_case_id = case.case_id

            db.session.add(note)

            note = call_modules_hook('on_postload_note_create', data=note, caseid=case.case_id)

            if not note:
                logs.append("Unable to add property for internal reasons")
                break
    return logs


def webhook_populate_payload_schema(case: Cases, webhook: Webhook):
    logs = []
    # Update webhook tasks
    if webhook.payload_schema:
        webhook.payload_schema = webhook.payload_schema

    for payload_schema_hook in webhook.payload_schema:
        try:
            # validate before saving
            payload_schema_hook = CaseNoteDirectorySchema()

            # Remap case task template fields
            # Set status to "To Do" which is ID 1
            mapped_payload_schema_hook = {
                "name": payload_schema_hook['title'],
                "parent_id": None,
                "case_id": case.case_id
            }

            payload_schema = payload_schema_hook.load(mapped_payload_schema_hook)
            db.session.add(payload_schema)
            db.session.commit()

            if not payload_schema:
                logs.append("Unable to add payload schema for internal reasons")
                break

            logs = webhook_populate_properties(case, payload_schema_hook, payload_schema)

        except marshmallow.exceptions.ValidationError as e:
            logs.append(e.messages)

    return logs


def webhook_post_modifier(case: Cases, webhook_id: Union[str, int]):
    webhook = get_webhook_by_id(int(webhook_id))
    logs = []
    if not webhook:
        logs.append(f"Webhook {webhook_id} not found")
        return None, logs

    # Update summary, we want to append in order not to skip the initial case description
    case.description += "\n" + webhook.summary

    # Update case tags
    for tag_str in webhook.tags:
        tag = Tags(tag_title=tag_str)
        tag = tag.save()
        case.tags.append(tag)

    # Update case tasks
    logs = webhook_populate_header_auth(case, webhook)
    if logs:
        return case, logs

    # Update case note groups
    logs = webhook_populate_payload_schema(case, webhook)
    if logs:
        return case, logs

    db.session.commit()

    return case, logs
