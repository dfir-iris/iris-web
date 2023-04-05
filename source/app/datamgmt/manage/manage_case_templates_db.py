#!/usr/bin/env python3
#
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
from typing import List, Optional

from app.models import CaseTemplate
from app.models.authorization import User


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
            if not isinstance(data["note_groups"], list):
                return "Note groups must be a list."
            for note_group in data["note_groups"]:
                if not isinstance(note_group, dict):
                    return "Each note group must be a dictionary."
                if "title" not in note_group:
                    return "Each note group must have a 'title' field."
                if "notes" in note_group:
                    if not isinstance(note_group["notes"], list):
                        return "Notes must be a list."
                    for note in note_group["notes"]:
                        if not isinstance(note, dict):
                            return "Each note must be a dictionary."
                        if "title" not in note:
                            return "Each note must have a 'title' field."

        # If all checks succeeded, we return None to indicate everything is has been validated
        return None
    except Exception as e:
        return str(e)
