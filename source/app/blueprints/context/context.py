#!/usr/bin/env python3
#
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

# IMPORTS ------------------------------------------------
from app import app
from app import db
from app.models.cases import Cases
from app.models.models import Client
from app.util import response_success, get_urlcasename

from flask_login import current_user
from flask import request, url_for, redirect
from flask import Blueprint


# CONTENT ------------------------------------------------
ctx_blueprint = Blueprint('context',
                                __name__,
                                template_folder='templates')


@ctx_blueprint.route('/context/set', methods=['POST'])
def set_ctx():
    """
    Set the context elements of a user i.e the current case
    :return: Page
    """
    if not current_user.is_authenticated:
        return redirect(url_for('login.login'))

    ctx = request.form.get('ctx')
    ctx_h = request.form.get('ctx_h')

    current_user.ctx_case = ctx
    current_user.ctx_human_case = ctx_h

    db.session.commit()

    update_user_case_ctx()

    return response_success(msg="Saved")


@app.context_processor
def iris_version():
    return dict(iris_version=app.config.get('IRIS_VERSION'))


@app.context_processor
def case_name():
    return dict(case_name=get_urlcasename())


@app.context_processor
def cases_context():
    # Get all investigations not closed
    res = Cases.query.with_entities(
        Cases.name,
        Client.name,
        Cases.case_id,
        Cases.close_date)\
        .join(Cases.client)\
        .filter(Cases.close_date == None)\
        .order_by(Cases.name)\
        .all()

    datao = [row for row in res]

    res = Cases.query.with_entities(
        Cases.name,
        Client.name,
        Cases.case_id,
        Cases.close_date)\
        .join(Cases.client)\
        .filter(Cases.close_date != None)\
        .order_by(Cases.name)\
        .all()

    datac = [row for row in res]

    return dict(cases_context_selector=datao,cases_close_context_selector=datac)


def update_user_case_ctx():
    """
    Retrieve a list of cases for the case selector
    :return:
    """
    # Get all investigations not closed
    res = Cases.query.with_entities(
        Cases.name,
        Client.name,
        Cases.case_id,
        Cases.close_date)\
        .join(Cases.client)\
        .order_by(Cases.open_date)\
        .all()

    data = [row for row in res]

    if current_user and current_user.ctx_case:
        # If the current user have a current case,
        # Look for it in the fresh list. If not
        # exists then remove from the user context
        is_found = False
        for row in data:
            if row[2] == current_user.ctx_case:
                is_found = True
                break

        if not is_found:
            # The case do not exists,
            # Removes it from the context
            current_user.ctx_case = None
            current_user.ctx_human_case = "Not set"
            db.session.commit()
            #current_user.save()

    app.jinja_env.globals.update({
        'cases_context_selector': data
    })

    return data

