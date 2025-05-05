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
import requests
import jsonschema
from datetime import datetime
from typing import List, Optional, Union
from app import db
from app.datamgmt.case.case_tasks_db import add_task, get_task
from app.datamgmt.manage.manage_case_classifications_db import get_case_classification_by_name
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.models.cases import Cases
from app.models.models import CaseTemplate
from app.models.models import Tags
from app.models.models import NoteDirectory
from app.models.authorization import User
from app.schema.marshables import CaseSchema, CaseTaskSchema, CaseNoteDirectorySchema, CaseNoteSchema
from app.datamgmt.manage.manage_webhooks_db import get_webhook_by_id


def get_case_templates_list() -> List[dict]:
    """Get a list of case templates

    Returns:
        List[dict]: List of case templates
    """
    case_templates = CaseTemplate.query.with_entities(
        CaseTemplate.id,
        CaseTemplate.name,
        CaseTemplate.display_name,
        CaseTemplate.description,
        CaseTemplate.title_prefix,
        CaseTemplate.author,
        CaseTemplate.created_at,
        CaseTemplate.classification,
        CaseTemplate.updated_at,
        User.name.label('added_by')
    ).join(
        CaseTemplate.created_by_user
    ).all()

    c_cl = [row._asdict() for row in case_templates]
    return c_cl


def get_case_template_by_id(cur_id: int) -> CaseTemplate:
    """Get a case template

    Args:
        cur_id (int): case template id

    Returns:
        CaseTemplate: Case template
    """
    case_template = CaseTemplate.query.filter_by(id=cur_id).first()
    return case_template


def delete_case_template_by_id(case_template_id: int):
    """Delete a case template

    Args:
        case_template_id (int): case template id
    """
    CaseTemplate.query.filter_by(id=case_template_id).delete()

def validate_case_template(data: dict, update: bool = False) -> Optional[str]:
    try:
        # Check that the 'name' field is provided and not empty
        if not update:
            if "name" not in data:
                return "<div><p><strong>Error:</strong> The 'name' field is required.</p></div>"
        if "name" in data and not data["name"].strip():
            return "<div><p><strong>Error:</strong> The 'name' field cannot be empty.</p></div>"

        # Validate 'tags' field
        if "tags" in data:
            if not isinstance(data["tags"], list):
                return "<div><p><strong>Error:</strong> 'tags' must be a list.</p></div>"
            for tag in data["tags"]:
                if not isinstance(tag, str):
                    return "<div><p><strong>Error:</strong> Each tag must be a string.</p></div>"

        # Validate 'tasks' field
        if "tasks" in data:
            if not isinstance(data["tasks"], list):
                return "<div><p><strong>Error:</strong> 'tasks' must be a list.</p></div>"
            for task in data["tasks"]:
                if not isinstance(task, dict):
                    return "<div><p><strong>Error:</strong> Each task must be a dictionary.</p></div>"
                if "title" not in task:
                    return "<div><p><strong>Error:</strong> Each task must have a 'title' field.</p></div>"
                if "tags" in task:
                    if not isinstance(task["tags"], list):
                        return "<div><p><strong>Error:</strong> Task tags must be a list.</p></div>"
                    for tag in task["tags"]:
                        if not isinstance(tag, str):
                            return "<div><p><strong>Error:</strong> Each task tag must be a string.</p></div>"
                if "actions" in task:
                    if not isinstance(task["actions"], list):
                        return "<div><p><strong>Error:</strong> Actions must be a list.</p></div>"
                    for action in task["actions"]:
                        if not isinstance(action, dict):
                            return "<div><p><strong>Error:</strong> Each action must be a dictionary.</p></div>"
                        if "webhook_id" not in action:
                            return "<div><p><strong>Error:</strong> Each action must have a 'webhook_id' field.</p></div>"
                        if "display_name" not in action:
                            return "<div><p><strong>Error:</strong> Each action must have a 'display_name' field.</p></div>"

                        # Validate webhook_id type (must be an integer)
                        if not isinstance(action["webhook_id"], int):
                            return f"<div><p><strong>Error:</strong> 'webhook_id' must be an integer, but got {type(action['webhook_id']).__name__}.</p></div>"

                        # Check if webhook exists for the given webhook_id
                        webhook = get_webhook_by_id(action["webhook_id"])
                        if not webhook:
                            return f"<div><p><strong>Error:</strong> Webhook with id {action['webhook_id']} does not exist.</p></div>"

        # Validate 'triggers' field
        if "triggers" in data:
            if not isinstance(data["triggers"], list):
                return "<div><p><strong>Error:</strong> 'triggers' must be a list.</p></div>"
            for trigger in data["triggers"]:
                if not isinstance(trigger, dict):
                    return "<div><p><strong>Error:</strong> Each trigger must be a dictionary.</p></div>"
                if "webhook_id" not in trigger:
                    return "<div><p><strong>Error:</strong> Each trigger must have a 'webhook_id' field.</p></div>"
                if "display_name" not in trigger:
                    return "<div><p><strong>Error:</strong> Each trigger must have a 'display_name' field.</p></div>"

                # Validate webhook_id type (must be an integer)
                if not isinstance(trigger["webhook_id"], int):
                    return f"<div><p><strong>Error:</strong> 'webhook_id' must be an integer, but got {type(trigger['webhook_id']).__name__}.</p></div>"

                # Check if webhook exists for the given webhook_id
                webhook = get_webhook_by_id(trigger["webhook_id"])
                if not webhook:
                    return f"<div><p><strong>Error:</strong> Webhook with id {trigger['webhook_id']} does not exist.</p></div>"

                # Validate 'input_params' field
                if "input_params" in trigger:
                    input_params = trigger["input_params"]
                    if not isinstance(input_params, dict):
                        return "<div><p><strong>Error:</strong> 'input_params' must be a dictionary.</p></div>"

                    payload_schema = webhook.payload_schema
                    if not payload_schema:
                        return f"<div><p><strong>Error:</strong> Webhook {webhook.name} has no payload schema.</p></div>"

                    # Validate required fields in payload_schema
                    required_fields = payload_schema.get("items", {}).get("required", [])
                    for field in required_fields:
                        if field not in input_params:
                            return f"<div><p><strong>Error:</strong> Field '{field}' is required in 'input_params' for webhook '{webhook.name}'.</p></div>"

                    # Validate properties in 'input_params'
                    properties = payload_schema.get("items", {}).get("properties", {})
                    for key, value in input_params.items():
                        if key not in properties:
                            return f"<div><p><strong>Error:</strong> Field '{key}' is not valid for webhook '{webhook.name}'.</p></div>"
                        prop_schema = properties[key]
                        TYPE_MAPPING = {
                            "string": str,
                            "integer": int,
                            "boolean": bool,
                            "array": list,
                            "object": dict,
                        }
                        expected_type = prop_schema.get("type")
                        if expected_type:
                            python_type = TYPE_MAPPING.get(expected_type)
                            if not python_type:
                                return f"<div><p><strong>Error:</strong> Unsupported type '{expected_type}' in schema for field '{key}'.</p></div>"
                            if not isinstance(value, python_type):
                                return f"<div><p><strong>Error:</strong> Field '{key}' must be of type '{expected_type}'.</p></div>"

                        # Validate minLength property
                        if prop_schema.get("minLength") and len(value) < prop_schema["minLength"]:
                            return f"<div><p><strong>Error:</strong> Field '{key}' must have at least {prop_schema['minLength']} characters.</p></div>"

        # Validate 'note_groups' field (deprecated)
        if "note_groups" in data:
            return "<div><p><strong>Error:</strong> 'note_groups' has been replaced by 'note_directories'.</p></div>"

        # Validate 'note_directories' field
        if "note_directories" in data:
            if not isinstance(data["note_directories"], list):
                return "<div><p><strong>Error:</strong> 'note_directories' must be a list.</p></div>"
            for note_dir in data["note_directories"]:
                if not isinstance(note_dir, dict):
                    return "<div><p><strong>Error:</strong> Each note directory must be a dictionary.</p></div>"
                if "title" not in note_dir:
                    return "<div><p><strong>Error:</strong> Each note directory must have a 'title' field.</p></div>"
                if "notes" in note_dir:
                    if not isinstance(note_dir["notes"], list):
                        return "<div><p><strong>Error:</strong> 'notes' must be a list.</p></div>"
                    for note in note_dir["notes"]:
                        if not isinstance(note, dict):
                            return "<div><p><strong>Error:</strong> Each note must be a dictionary.</p></div>"
                        if "title" not in note:
                            return "<div><p><strong>Error:</strong> Each note must have a 'title' field.</p></div>"

        return None
    except Exception as e:
        return f"<div><p><strong>Error:</strong> An unexpected error occurred:</p><pre>{str(e)}</pre></div>"



def case_template_pre_modifier(case_schema: CaseSchema, case_template_id: str):
    case_template = get_case_template_by_id(int(case_template_id))
    if not case_template:
        return None
    if case_template.title_prefix:
        case_schema.name = case_template.title_prefix + " " + case_schema.name[0]

    case_classification = get_case_classification_by_name(case_template.classification)
    if case_classification:
        case_schema.classification_id = case_classification.id

    return case_schema

def case_template_populate_tasks(case: Cases, case_template: CaseTemplate):
    logs = []
    # Update case tasks
    for task_template in case_template.tasks:
        try:
            # validate before saving
            task_schema = CaseTaskSchema()

            # Remap case task template fields
            # Set status to "To Do" which is ID 1
            mapped_task_template = {
                "task_title": task_template['title'],
                "task_description": task_template['description'] if task_template.get('description') else "",
                "task_tags": ",".join(tag for tag in task_template["tags"]) if task_template.get('tags') else "",
                "task_status_id": 1,
                "task_actions": [
                    {
                        "webhook_id": action["webhook_id"],
                        "display_name": action["display_name"]
                    } for action in task_template.get("actions", [])
                ]
            }

            mapped_task_template = call_modules_hook('on_preload_task_create', data=mapped_task_template, caseid=case.case_id)

            task = task_schema.load(mapped_task_template)

            assignee_id_list = []

            ctask = add_task(task=task,
                             assignee_id_list=assignee_id_list,
                             user_id=case.user_id,
                             caseid=case.case_id
                             )

            ctask = call_modules_hook('on_postload_task_create', data=ctask, caseid=case.case_id)

            if not ctask:
                logs.append("Unable to create task for internal reasons")

        except marshmallow.exceptions.ValidationError as e:
            logs.append(e.messages)

    return logs


def case_template_populate_notes(case: Cases, note_dir_template: dict, ng: NoteDirectory):
    logs = []
    if note_dir_template.get("notes"):
        for note_template in note_dir_template["notes"]:
            # validate before saving
            note_schema = CaseNoteSchema()

            mapped_note_template = {
                "directory_id": ng.id,
                "note_title": note_template["title"],
                "note_content": note_template["content"] if note_template.get("content") else ""
            }

            mapped_note_template = call_modules_hook('on_preload_note_create',
                                                     data=mapped_note_template,
                                                     caseid=case.case_id)

            note_schema.verify_directory_id(mapped_note_template, caseid=ng.case_id)
            note = note_schema.load(mapped_note_template)

            note.note_creationdate = datetime.utcnow()
            note.note_lastupdate = datetime.utcnow()
            note.note_user = case.user_id
            note.note_case_id = case.case_id

            db.session.add(note)

            note = call_modules_hook('on_postload_note_create', data=note, caseid=case.case_id)

            if not note:
                logs.append("Unable to add note for internal reasons")
                break
    return logs


def case_template_populate_note_groups(case: Cases, case_template: CaseTemplate):
    logs = []
    # Update case tasks
    if case_template.note_directories:
        case_template.note_directories = case_template.note_directories

    for note_dir_template in case_template.note_directories:
        try:
            # validate before saving
            note_dir_schema = CaseNoteDirectorySchema()

            # Remap case task template fields
            # Set status to "To Do" which is ID 1
            mapped_note_dir_template = {
                "name": note_dir_template['title'],
                "parent_id": None,
                "case_id": case.case_id
            }

            note_dir = note_dir_schema.load(mapped_note_dir_template)
            db.session.add(note_dir)
            db.session.commit()

            if not note_dir:
                logs.append("Unable to add note group for internal reasons")
                break

            logs = case_template_populate_notes(case, note_dir_template, note_dir)

        except marshmallow.exceptions.ValidationError as e:
            logs.append(e.messages)

    return logs


def case_template_post_modifier(case: Cases, case_template_id: Union[str, int]):
    case_template = get_case_template_by_id(int(case_template_id))
    logs = []
    if not case_template:
        logs.append(f"Case template {case_template_id} not found")
        return None, logs

    # Update summary, we want to append in order not to skip the initial case description
    case.description += "\n" + case_template.summary

    # Update case tags
    for tag_str in case_template.tags:
        tag = Tags(tag_title=tag_str)
        tag = tag.save()
        case.tags.append(tag)

    # Update case tasks
    logs = case_template_populate_tasks(case, case_template)
    if logs:
        return case, logs

    # Update case note groups
    logs = case_template_populate_note_groups(case, case_template)
    if logs:
        return case, logs

    db.session.commit()

    return case, logs


def get_triggers_by_case_template_id(case_template_id) -> CaseTemplate:
    """
    Retrieves the triggers array for a given case_template_id.

    :param case_template_id: The ID of the case template to look up.
    :param db_session: SQLAlchemy database session.
    :return: A list of triggers or an empty list if none are found.
    """

    case_template = CaseTemplate.query.filter_by(id=case_template_id).first()

    if not case_template:
        return []


    return case_template.triggers or []

def get_action_by_case_template_id_and_task_id(case_template_id, task_id, caseid) -> list:
    """
    Retrieves the actions array for a given case_template_id and task_id.

    :param case_template_id: The ID of the case template to look up.
    :param task_id: The ID of the task to look up within the case template.
    :return: A list of actions or an empty list if none are found.
    """

    case_template = CaseTemplate.query.filter_by(id=case_template_id).first()
    case_task = get_task(task_id=task_id)
    if not case_template:
        return []

    actions = []

    for task in case_template.tasks:

        if case_task.task_title == task["title"]:
           if 'actions' in task:

            for action in task['actions']:
                actions.append(dict(action))

    return actions


