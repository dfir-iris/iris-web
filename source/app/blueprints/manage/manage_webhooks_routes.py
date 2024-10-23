import json
from flask import Blueprint, redirect, render_template, request, url_for
from app import db
from app.models.authorization import Permissions
from app.util import ac_api_requires, ac_requires, response_error, response_success

manage_webhooks_blueprint = Blueprint('manage_webhooks', __name__, template_folder='templates')

# CONTENT ------------------------------------------------
@manage_webhooks_blueprint.route('/manage/webhooks')
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_webhooks(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_webhooks.manage_webhooks', cid=caseid))

    return render_template('manage_webhooks.html')


