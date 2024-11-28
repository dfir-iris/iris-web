# IMPORTS ------------------------------------------------
from flask import Blueprint, request, redirect, render_template, url_for
import json
from flask_wtf import FlaskForm
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_case_response_db import get_case_responses_list

case_triggers_blueprint = Blueprint('case_triggers',
                                    __name__,
                                    template_folder='templates')

@case_triggers_blueprint.route('/case/triggers', methods=['GET'])
def case_triggers():
    # Retrieve query parameters from the URL
    caseid = request.args.get('caseid')
    url_redir = request.args.get('url_redir', type=bool)

    if url_redir:
        return redirect(url_for('case_triggers.case_triggers', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)
    triggers = get_case_responses_list()

    # Serialize datetime objects for rendering
    for trigger in triggers:
        trigger['created_at'] = trigger['created_at'].strftime("%Y-%m-%d %H:%M:%S")
        if trigger['updated_at']:
            trigger['updated_at'] = trigger['updated_at'].strftime("%Y-%m-%d %H:%M:%S")
        if trigger['body']:
            try:
                trigger['body'] = json.dumps(trigger['body'])
            except (TypeError, ValueError) as e:
                trigger['body'] = str(trigger['body'])  # Fallback to string representation

    return render_template("case_triggers.html", case=case, form=form, triggers=triggers)