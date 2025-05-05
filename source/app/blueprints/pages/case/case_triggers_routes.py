# IMPORTS ------------------------------------------------
from flask import Blueprint, jsonify, request, redirect, render_template, url_for
import json
from flask_wtf import FlaskForm
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_case_response_db import get_case_responses_list_by_case_id

case_triggers_blueprint = Blueprint('case_triggers',
                                    __name__,
                                    template_folder='templates')

@case_triggers_blueprint.route('/case/triggers', methods=['GET'])
def case_triggers():
    # Retrieve query parameters from the URL
    caseid = request.args.get('cid')
    url_redir = request.args.get('url_redir', type=bool)

    if url_redir:
        return redirect(url_for('case_triggers.case_triggers', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)
    return render_template("case_triggers.html", case=case, form=form)


@case_triggers_blueprint.route('/case/triggers-list/<int:cur_id>', methods=['GET'])
def case_triggers_list(cur_id):

    try:
        # Retrieve the triggers list
        triggers = get_case_responses_list_by_case_id(cur_id)
        # Serialize datetime objects for rendering
        for trigger in triggers:
            # Format created_at
            if 'created_at' in trigger and trigger['created_at']:
                trigger['created_at'] = trigger['created_at'].strftime("%Y-%m-%d %H:%M:%S")

            # Format updated_at
            if 'updated_at' in trigger and trigger['updated_at']:
                trigger['updated_at'] = trigger['updated_at'].strftime("%Y-%m-%d %H:%M:%S")

            # Serialize body
            if 'body' in trigger and trigger['body']:
                try:
                    trigger['body'] = json.dumps(trigger['body'])
                except (TypeError, ValueError):
                    trigger['body'] = str(trigger['body'])  # Fallback to string representation

        # Return the JSON response
        return jsonify({"success": True, "data": triggers})

    except Exception as e:
        # Log the exception for debugging (optional: use a logger instead of print)
        print(f"Error processing case triggers: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
