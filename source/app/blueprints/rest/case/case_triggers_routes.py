#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS) - DFIR-IRIS Team
#  ir@cyberactionlab.net - contact@dfir-iris.org
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

# IMPORTS ------------------------------------------------
from flask import Blueprint, jsonify, request, redirect, render_template, url_for
import json
from flask_wtf import FlaskForm
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_task_response_db import get_task_responses_list_for_case
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.models.authorization import CaseAccessLevel

case_triggers_blueprint = Blueprint('case_triggers',
                                    __name__,
                                    template_folder='templates')

@case_triggers_blueprint.route('/case/triggers', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_triggers(caseid):
    # Page route uses ac_requires_case_identifier which only injects 'caseid'
    form = FlaskForm()
    case = get_case(caseid)

    if case is None:
        return render_template("case_triggers.html", case=None, caseid=caseid, form=form)

    return render_template("case_triggers.html", case=case, caseid=caseid, form=form)


@case_triggers_blueprint.route('/case/triggers-list/<int:case_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_triggers_list(case_id, caseid):
    # case_id path param should match resolved caseid
    if case_id != caseid:
        return jsonify({"success": False, "error": "Inconsistent case id"}), 400
    try:
        responses = get_task_responses_list_for_case(caseid)
        # Normalize field names to match tasks tab expectations
        normalized = []
        for r in responses:
            normalized.append({
                'id': r.get('id'),
                'action_id': r.get('action_id') or r.get('action'),
                'task_id': r.get('task_id') or r.get('task'),
                'body': json.dumps(r.get('body')) if isinstance(r.get('body'), dict) else r.get('body'),
                'created_at': r.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if r.get('created_at') else None,
                'created_by': r.get('created_by')
            })
        return jsonify({"success": True, "data": normalized})
    except Exception as e:
        print(f"Error processing case triggers: {e}")
        return jsonify({"success": False, "error": str(e)}), 500