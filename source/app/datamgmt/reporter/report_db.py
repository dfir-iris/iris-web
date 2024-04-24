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
import datetime
import re

from sqlalchemy import desc

from app.business.iocs import get_iocs
from app.datamgmt.case.case_notes_db import get_notes_from_group, get_case_note_comments
from app.datamgmt.case.case_tasks_db import get_tasks_with_assignees
from app.models import AnalysisStatus, CompromiseStatus, TaskAssignee, NotesGroupLink
from app.models import AssetsType
from app.models import CaseAssets
from app.models import CaseEventsAssets
from app.models import CaseEventsIoc
from app.models import CaseReceivedFile
from app.models import CaseStatus
from app.models import CaseTasks
from app.models import Cases
from app.models import CasesEvent
from app.models import Client
from app.models import Comments
from app.models import EventCategory
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocLink
from app.models import IocType
from app.models import Notes
from app.models import NotesGroup
from app.models import TaskStatus
from app.models import Tlp
from app.models.authorization import User
from app.schema.marshables import CaseDetailsSchema, CommentSchema, CaseNoteSchema, IocSchema


def export_case_json(case_id):
    """
    Fully export a case a JSON
    """
    export = {}
    case = export_caseinfo_json(case_id)

    if not case:
        export['errors'] = ["Invalid case number"]
        return export

    case['description'] = process_md_images_links_for_report(case['description'])

    export['case'] = case
    export['evidences'] = export_case_evidences_json(case_id)
    export['timeline'] = export_case_tm_json(case_id)
    export['iocs'] = export_case_iocs_json(case_id)
    export['assets'] = export_case_assets_json(case_id)
    export['tasks'] = export_case_tasks_json(case_id)
    export['comments'] = export_case_comments_json(case_id)
    export['notes'] = export_case_notes_json(case_id)
    export['export_date'] = datetime.datetime.utcnow()

    return export


def export_case_json_for_report(case_id):
    """
    Fully export of a case for report generation
    """
    export = {}
    case = export_caseinfo_json(case_id)

    if not case:
        export['errors'] = ["Invalid case number"]
        return export

    case['description'] = process_md_images_links_for_report(case['description'])

    export['case'] = case
    export['evidences'] = export_case_evidences_json(case_id)
    export['timeline'] = export_case_tm_json(case_id)
    export['iocs'] = export_case_iocs_json(case_id)
    export['assets'] = export_case_assets_json(case_id)
    export['tasks'] = export_case_tasks_json(case_id)
    export['notes'] = export_case_notes_json(case_id)
    export['comments'] = export_case_comments_json(case_id)
    export['export_date'] = datetime.datetime.utcnow()

    return export


def export_case_json_extended(case_id):
    """
    Export a case a JSON
    """
    export = {}
    case = export_caseinfo_json_extended(case_id)

    if not case:
        export['errors'] = ["Invalid case number"]
        return export

    export['case'] = case
    export['evidences'] = export_case_evidences_json_extended(case_id)
    export['timeline'] = export_case_tm_json_extended(case_id)
    export['iocs'] = export_case_iocs_json_extended(case_id)
    export['assets'] = export_case_assets_json_extended(case_id)
    export['tasks'] = export_case_tasks_json_extended(case_id)
    export['notes'] = export_case_notes_json_extended(case_id)
    export['export_date'] = datetime.datetime.utcnow()

    return export


def process_md_images_links_for_report(markdown_text):
    """Process images links in markdown for better processing on the generator side
        Creates proper links with FQDN and removal of scale
    """
    markdown = re.sub(r'(/datastore\/file\/view\/\d+\?cid=\d+)( =[\dA-z%]*)\)',
                      r"http://127.0.0.1:8000:/\1)", markdown_text)
    return markdown


def export_caseinfo_json_extended(case_id):
    case = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    return case


def export_case_evidences_json_extended(case_id):
    evidences = CaseReceivedFile.query.filter(
        CaseReceivedFile.case_id == case_id
    ).join(
        CaseReceivedFile.case
    ).join(
        CaseReceivedFile.user).all()

    return evidences


def export_case_tm_json_extended(case_id):
    events = CasesEvent.query.filter(
        CasesEvent.case_id == case_id
    ).all()

    return events


def export_case_iocs_json_extended(case_id):
    iocs = Ioc.query.filter(
        IocLink.case_id == case_id
    ).all()

    return iocs


def export_case_assets_json_extended(case_id):
    assets = CaseAssets.query.filter(
        CaseAssets.case_id == case_id
    ).all()

    return assets


def export_case_tasks_json_extended(case_id):
    tasks = CaseTasks.query.filter(
        CaseTasks.task_case_id == case_id
    ).all()

    return tasks


def export_case_notes_json_extended(case_id):
    notes_groups = NotesGroup.query.filter(
        NotesGroup.group_case_id == case_id
    ).all()

    for notes_group in notes_groups:
        notes_group = notes_group.__dict__
        notes_group['notes'] = get_notes_from_group(notes_group['group_id'], case_id)

    return notes_groups


def export_caseinfo_json(case_id):

    case = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    if not case:
        return None

    case = CaseDetailsSchema().dump(case)

    return case


def export_case_evidences_json(case_id):
    evidences = CaseReceivedFile.query.filter(
        CaseReceivedFile.case_id == case_id
    ).with_entities(
        CaseReceivedFile.filename,
        CaseReceivedFile.date_added,
        CaseReceivedFile.file_hash,
        User.name.label('added_by'),
        CaseReceivedFile.custom_attributes,
        CaseReceivedFile.file_uuid,
        CaseReceivedFile.id,
        CaseReceivedFile.file_size,
    ).order_by(
        CaseReceivedFile.date_added
    ).join(
        CaseReceivedFile.user
    ).all()

    if evidences:

        return [row._asdict() for row in evidences]

    else:
        return []


def export_case_notes_json(case_id):
    # Fetch all notes associated with the case
    notes = Notes.query.filter(
        Notes.note_case_id == case_id
    ).all()

    # Initialize the schemas
    note_schema = CaseNoteSchema()
    comments_schema = CommentSchema(many=True)

    # Serialize the notes and their comments
    serialized_notes = []
    for note in notes:
        note_comments = get_case_note_comments(note.note_id)
        serialized_note = note_schema.dump(note)
        serialized_note['comments'] = comments_schema.dump(note_comments)
        serialized_note["note_content"] = process_md_images_links_for_report(serialized_note["note_content"])

        serialized_notes.append(serialized_note)

    return serialized_notes


def export_case_tm_json(case_id):
    timeline = CasesEvent.query.with_entities(
        CasesEvent.event_id,
        CasesEvent.event_title,
        CasesEvent.event_in_summary,
        CasesEvent.event_date,
        CasesEvent.event_tz,
        CasesEvent.event_date_wtz,
        CasesEvent.event_content,
        CasesEvent.event_tags,
        CasesEvent.event_source,
        CasesEvent.event_raw,
        CasesEvent.custom_attributes,
        EventCategory.name.label('category'),
        User.name.label('last_edited_by'),
        CasesEvent.event_uuid,
        CasesEvent.event_in_graph,
        CasesEvent.event_in_summary,
        CasesEvent.event_color,
        CasesEvent.event_is_flagged
    ).filter(
        CasesEvent.case_id == case_id
    ).order_by(
        CasesEvent.event_date
    ).join(
        CasesEvent.user
    ).outerjoin(
        CasesEvent.category
    ).all()

    tim = []
    for row in timeline:
        ras = row._asdict()
        ras['assets'] = None

        as_list = CaseEventsAssets.query.with_entities(
            CaseAssets.asset_id,
            CaseAssets.asset_name,
            AssetsType.asset_name.label('type')
        ).filter(
            CaseEventsAssets.event_id == row.event_id
        ).join(
            CaseEventsAssets.asset
        ).join(
            CaseAssets.asset_type
        ).all()

        alki = []
        for asset in as_list:
            alki.append("{} ({})".format(asset.asset_name, asset.type))

        ras['assets'] = alki

        iocs_list = CaseEventsIoc.query.with_entities(
            CaseEventsIoc.ioc_id,
            Ioc.ioc_value,
            Ioc.ioc_description,
            Tlp.tlp_name,
            IocType.type_name.label('type')
        ).filter(
            CaseEventsIoc.event_id == row.event_id
        ).join(
            CaseEventsIoc.ioc
        ).join(
            Ioc.ioc_type
        ).join(
            Ioc.tlp
        ).all()

        ras['iocs'] = [ioc._asdict() for ioc in iocs_list]

        tim.append(ras)

    return tim


def export_case_iocs_json(case_id):
    iocs = get_iocs(case_id)

    iocs_serialized = IocSchema().dump(iocs, many=True)

    return iocs_serialized


def export_case_tasks_json(case_id):
    res = CaseTasks.query.with_entities(
        CaseTasks.task_title,
        TaskStatus.status_name.label('task_status'),
        CaseTasks.task_tags,
        CaseTasks.task_open_date,
        CaseTasks.task_close_date,
        CaseTasks.task_last_update,
        CaseTasks.task_description,
        CaseTasks.custom_attributes,
        CaseTasks.task_uuid,
        CaseTasks.id
    ).filter(
        CaseTasks.task_case_id == case_id
    ).join(
       CaseTasks.status
    ).all()

    tasks = [c._asdict() for c in res]

    task_with_assignees = []
    for task in tasks:
        task_id = task['id']
        get_assignee_list = TaskAssignee.query.with_entities(
            TaskAssignee.task_id,
            User.user,
            User.id,
            User.name
        ).join(
            TaskAssignee.user
        ).filter(
            TaskAssignee.task_id == task_id
        ).all()

        assignee_list = {}
        for member in get_assignee_list:
            if member.task_id not in assignee_list:

                assignee_list[member.task_id] = [{
                    'user': member.user,
                    'name': member.name,
                    'id': member.id
                }]
            else:
                assignee_list[member.task_id].append({
                    'user': member.user,
                    'name': member.name,
                    'id': member.id
                })
        task['task_assignees'] = assignee_list.get(task['id'], [])
        task_with_assignees.append(task)

    return task_with_assignees


def export_case_assets_json(case_id):
    ret = []

    res = CaseAssets.query.with_entities(
        CaseAssets.asset_id,
        CaseAssets.asset_uuid,
        CaseAssets.asset_name,
        CaseAssets.asset_description,
        CaseAssets.asset_compromise_status_id,
        AssetsType.asset_name.label("type"),
        AnalysisStatus.name.label('analysis_status'),
        CaseAssets.date_added,
        CaseAssets.asset_domain,
        CaseAssets.asset_ip,
        CaseAssets.asset_info,
        CaseAssets.asset_tags,
        CaseAssets.custom_attributes
    ).filter(
        CaseAssets.case_id == case_id
    ).join(
        CaseAssets.asset_type
    ).join(
        CaseAssets.analysis_status
    ).order_by(desc(CaseAssets.asset_compromise_status_id)).all()

    for row in res:
        row = row._asdict()
        row['light_asset_description'] = row['asset_description']

        ial = IocAssetLink.query.with_entities(
            Ioc.ioc_value,
            IocType.type_name,
            Ioc.ioc_description
        ).filter(
            IocAssetLink.asset_id == row['asset_id']
        ).join(
            IocAssetLink.ioc
        ).join(
            Ioc.ioc_type
        ).all()

        if ial:
            row['asset_ioc'] = [row._asdict() for row in ial]
        else:
            row['asset_ioc'] = []

        if row['asset_compromise_status_id'] is None:
            row['asset_compromise_status_id'] = CompromiseStatus.unknown.value
            status_text = CompromiseStatus.unknown.name.replace('_', ' ').title()
        else:
            status_text = CompromiseStatus(row['asset_compromise_status_id']).name.replace('_', ' ').title()

        row['asset_compromise_status'] = status_text

        ret.append(row)

    return ret


def export_case_comments_json(case_id):
    comments = Comments.query.with_entities(
        Comments.comment_id,
        Comments.comment_uuid,
        Comments.comment_text,
        User.name.label('comment_by'),
        Comments.comment_date,
    ).filter(
        Comments.comment_case_id == case_id
    ).join(
        Comments.user
    ).order_by(
        Comments.comment_date
    ).all()

    return [row._asdict() for row in comments]
