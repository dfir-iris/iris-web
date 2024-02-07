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
from app.models import CaseTemplate, Cases, Tags, NoteDirectory
from app.models.authorization import User
from app.schema.marshables import CaseSchema, CaseTaskSchema, CaseNoteDirectorySchema, CaseNoteSchema


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
            # If it's not an update, we check the required fields
            if "name" not in data:
                return "Name is required."

            if "display_name" not in data or not data["display_name"].strip():
                data["display_name"] = data["name"]
        # We check that name is not empty
        if "name" in data and not data["name"].strip():
            return "Name cannot be empty."

        # We check that author length is not above 128 chars
        if "author" in data and len(data["author"]) > 128:
            return "Author cannot be longer than 128 characters."

        # We check that author length is not above 128 chars
        if "author" in data and len(data["author"]) > 128:
            return "Author cannot be longer than 128 characters."

        # We check that prefix length is not above 32 chars
        if "title_prefix" in data and len(data["title_prefix"]) > 32:
            return "Prefix cannot be longer than 32 characters."

        # We check that tags, if any, are a list of strings
        if "tags" in data:
            if not isinstance(data["tags"], list):
                return "Tags must be a list."
            for tag in data["tags"]:
                if not isinstance(tag, str):
                    return "Each tag must be a string."

        # We check that tasks, if any, are a list of dictionaries with mandatory keys
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

        # We check that note groups, if any, are a list of dictionaries with mandatory keys
        if "note_groups" in data:
            return "Note groups has been replaced by note_directories."

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

        # If all checks succeeded, we return None to indicate everything is has been validated
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
                "task_status_id": 1
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
