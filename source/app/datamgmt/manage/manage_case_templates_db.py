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
from app.datamgmt.case.case_notes_db import add_note
from app.datamgmt.case.case_tasks_db import add_task
from app.datamgmt.manage.manage_case_classifications_db import get_case_classification_by_name
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.models import CaseTemplate, Cases, Tags, NoteDirectory, CaseResponse, TaskResponse
from app.models.authorization import User
from app.schema.marshables import CaseSchema, TaskResponseSchema, CaseTaskSchema, CaseNoteDirectorySchema, CaseNoteSchema
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
        if not update:
            if "name" not in data:
                return "Name is required."

        if "name" in data and not data["name"].strip():
            return "Name cannot be empty."

        if "tags" in data:
            if not isinstance(data["tags"], list):
                return "Tags must be a list."
            for tag in data["tags"]:
                if not isinstance(tag, str):
                    return "Each tag must be a string."
                    
                        
        if "tasks" in data:
            if not isinstance(data["tasks"], list):
                return "Tasks must be a list."
            for task in data["tasks"]:
                if not isinstance(task, dict):
                    return "Each task must be a dictionary."
                if "title" not in task:
                    return "Each task must have a 'title' field."
                if "tags" in task:
                    if not isinstance(task["tags"], list):
                        return "Task tags must be a list."
                    for tag in task["tags"]:
                        if not isinstance(tag, str):
                            return "Each tag must be a string."
                if "actions" in task:
                    if not isinstance(task["actions"], list):
                        return "Actions must be a list."
                    for action in task["actions"]:
                        if not isinstance(action, dict):
                            return "Each action must be a dictionary."
                        # Check for required properties
                        if "webhook_id" not in action:
                            return "Each action must have a 'webhook_id' field."
                        if "display_name" not in action:
                            return "Each action must have a 'display_name' field."
                        # Check for extra properties
                        allowed_keys = {"webhook_id", "display_name"}
                        extra_keys = set(action.keys()) - allowed_keys
                        if extra_keys:
                            return f"Invalid properties in action: {', '.join(extra_keys)}. Only 'webhook_id' and 'display_name' are allowed."
                        webhook = get_webhook_by_id(action["webhook_id"])
                        if not webhook:
                            return f"Webhook with id {action['webhook_id']} does not exist."


        if "triggers" in data:
            if not isinstance(data["triggers"], list):
                return "Trigger must be a list."
            for trigger in data["triggers"]:
                if not isinstance(trigger, dict):
                    return "Each trigger must be a dictionary."
                if "webhook_id" not in trigger:
                    return "Each trigger must have a 'webhook_id' field."
                if "display_name" not in trigger:
                    return "Each trigger must have a 'display_name' field."

                webhook = get_webhook_by_id(trigger["webhook_id"])
                if not webhook:
                    return f"Webhook with id {trigger['webhook_id']} does not exist."

                if "input_params" in trigger:
                    input_params = trigger["input_params"]
                    if not isinstance(input_params, dict):
                        return "input_params must be a dictionary."

                    payload_schema = webhook.payload_schema
                    if not payload_schema:
                        return f"Webhook {webhook.name} has no payload schema."

                    # Validate required fields
                    required_fields = payload_schema.get("items", {}).get("required", [])
                    for field in required_fields:
                        if field not in input_params:
                            return f"Field '{field}' is required in input_params for webhook '{webhook.name}'."

                    # Validate properties
                    properties = payload_schema.get("items", {}).get("properties", {})
                    for key, value in input_params.items():
                        if key not in properties:
                            return f"Field '{key}' is not valid for webhook '{webhook.name}'."
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
                            # Map schema type to Python type
                            python_type = TYPE_MAPPING.get(expected_type)
                            if not python_type:
                                return f"Unsupported type '{expected_type}' in schema for field '{key}'."
                            if not isinstance(value, python_type):
                                return f"Field '{key}' must be of type '{expected_type}'."

                        if prop_schema.get("minLength") and len(value) < prop_schema["minLength"]:
                            return f"Field '{key}' must have at least {prop_schema['minLength']} characters."

        if "note_groups" in data:
            return "Note groups have been replaced by note_directories."

        if "note_directories" in data:
            if not isinstance(data["note_directories"], list):
                return "Note directories must be a list."
            for note_dir in data["note_directories"]:
                if not isinstance(note_dir, dict):
                    return "Each note directory must be a dictionary."
                if "title" not in note_dir:
                    return "Each note directory must have a 'title' field."
                if "notes" in note_dir:
                    if not isinstance(note_dir["notes"], list):
                        return "Notes must be a list."
                    for note in note_dir["notes"]:
                        if not isinstance(note, dict):
                            return "Each note must be a dictionary."
                        if "title" not in note:
                            return "Each note must have a 'title' field."

        return None
    except Exception as e:
        return str(e)


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


def execute_and_save_trigger(trigger, case_template_id):
    try:
        # Extract webhook_id from the trigger
        webhook_id = trigger.get("webhook_id")
        print(f"Webhook ID: {webhook_id}")  # Debugging: Ensure webhook_id is being accessed
        if not webhook_id:
            raise ValueError("Trigger execution failed: webhook_id is missing in trigger.")

        # Fetch the webhook object from the database
        webhook = get_webhook_by_id(webhook_id)
        print(f"Webhook Object: {webhook}")  # Debugging: Log the webhook object
        if not webhook:
            raise ValueError(f"Trigger execution failed: No webhook found for webhook_id {webhook_id}.")

        # Fetch the URL from the webhook object
        url = webhook.url  # Adjust this based on your webhook model's attributes
        print(f"Webhook URL: {url}")  # Debugging: Ensure URL is being accessed
        if not url:
            raise ValueError(f"Trigger execution failed: URL is missing in webhook with id {webhook_id}.")

        # Execute the webhook request
        print(f"Executing webhook request to URL: {url} with data: {trigger}")
        response = requests.post(url, json=trigger)
        print(f"Webhook Response Status Code: {response.status_code}")  # Log response status
        print(f"Webhook Response Content: {response.text}")  # Log response content

        # Check response status
        if response.status_code == 200:
            results = response.json()
            print(f"Webhook Execution Results: {results}")  # Log the result of the execution
            save_results(results, case_template_id, webhook_id)  # Assuming save_results is implemented to handle the output
            return f"Trigger executed successfully and saved for webhook_id {webhook_id}."
        else:
            raise ValueError(
                f"Trigger execution failed: Webhook request returned status {response.status_code}, "
                f"response: {response.text}"
            )

    except Exception as e:
        print(f"Error in execute_and_save_trigger: {str(e)}")  # Log the error
        return str(e)


def save_results(data, case_template_id, webhook_id):
    """
    Save the results of a webhook execution into the CaseResponse model.
    
    :param data: The response data to save (JSON).
    :param case_template_id: The case template ID.
    :param webhook_id: The webhook ID.
    """
    try:
        # Create a new CaseResponse object
        case_response = CaseResponse(
            case=case_template_id,
            trigger=webhook_id,
            body=data,
        )
        
        # Add the object to the session and commit
        db.session.add(case_response)
        db.session.commit()
        
        print(case_response.id, case_response.case, case_response.trigger, case_response.body, case_response.execution_time)
        print(f"CaseResponse saved successfully with id {case_response.id}")
    except Exception as e:
        db.session.rollback()  # Roll back the session in case of an error
        print(f"Error saving CaseResponse: {str(e)}")


def execute_and_save_action(action, task_id, action_id):
    print("in execute function")
    try:
        # Extract webhook_id
        webhook_id = action_id
        print(f"Webhook ID: {webhook_id}")
        if not webhook_id:
            raise ValueError("Action execution failed: webhook_id is missing in action.")

        # Fetch webhook details
        webhook = get_webhook_by_id(webhook_id)
        print(f"Webhook Object: {webhook}")
        if not webhook:
            raise ValueError(f"Action execution failed: No webhook found for webhook_id {webhook_id}.")

        # Validate the webhook URL
        url = webhook.url
        print(f"Webhook URL: {url}")
        if not url:
            raise ValueError(f"Action execution failed: URL is missing in webhook with id {webhook_id}.")

        # Execute the webhook request
        print(f"Executing webhook request to URL: {url} with data: {action}")
        response = requests.post(url, json=action)
        print(f"Webhook Response Status Code: {response.status_code}")
        print(f"Webhook Response Content: {response.text}")

        # Validate and process the response
        if response.status_code == 200:
            if 'application/json' in response.headers.get('Content-Type', ''):
                results = response.json()
                print(f"Webhook Execution Results: {results}")

                # Save results in the database
                save_results_for_tasks(results, task_id, webhook_id)

                # Ensure results are a list of dictionaries
                if isinstance(results, dict):
                    results = [results]  # Wrap single dictionary in a list
                elif not isinstance(results, list):
                    raise ValueError("Unexpected response format: Expected a dictionary or a list of dictionaries.")

                return results
            else:
                raise ValueError("Webhook response is not in JSON format.")
        else:
            raise ValueError(
                f"Action execution failed: Webhook request returned status {response.status_code}, "
                f"response: {response.text}"
            )

    except Exception as e:
        print(f"Error in execute_and_save_action: {str(e)}")
        raise  # Propagate the exception for handling in the calling function



def save_results_for_tasks(data, task_id, webhook_id):
    """
    Save the results of an action execution into the TaskResponse model.
    :param data: The response data to save (JSON, list of dictionaries or dictionary).
    :param task_id: The task ID.
    :param webhook_id: The webhook ID.
    """
    try:
        # Ensure data is a list of dictionaries
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError("Unexpected data format: Expected a dictionary or list of dictionaries.")

        for item in data:
            # Create a new TaskResponse object for each result
            task_response = TaskResponse(
                task=task_id,
                action=webhook_id,
                body=item,  # Assuming item is JSON-serializable
            )

            # Add the object to the session
            db.session.add(task_response)

        # Commit all changes at once
        db.session.commit()

        print(f"TaskResponses saved successfully for task ID {task_id}")

    except Exception as e:
        db.session.rollback()  # Roll back the session in case of an error
        print(f"Error saving TaskResponse: {str(e)}")
        raise

