#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from flask import Blueprint
from flask import redirect
from flask import request

from app import app
from app import cache
from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.context.context_db import ctx_search_user_cases
from app.models.authorization import Permissions
from app.models.cases import Cases
from app.models.customers import Client
from app.blueprints.access_controls import ac_api_requires, not_authenticated_redirection_url
from app.blueprints.responses import response_success
from app.blueprints.rest.endpoints import endpoint_deprecated

context_rest_blueprint = Blueprint('context_rest', __name__)


@context_rest_blueprint.route('/context/search-cases', methods=['GET'])
@ac_api_requires()
def cases_context_search():
    search = request.args.get('q')

    # Get all investigations not closed
    datao = ctx_search_user_cases(search, iris_current_user.id, max_results=100)

    return response_success(data=datao)


# TODO why is this route not prefixed with annotation @ac_api_requires?
@context_rest_blueprint.route('/context/set', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/me')
def set_ctx():
    """
    Set the context elements of a user i.e the current case
    :return: Page
    """
    if not iris_current_user.is_authenticated:
        return redirect(not_authenticated_redirection_url(request.full_path))

    ctx = request.form.get('ctx')

    iris_current_user.ctx_case = ctx

    db.session.commit()

    _update_user_case_ctx()

    return response_success(msg="Saved")


# TODO should move this method somewhere else, it is not a REST route
@app.context_processor
def iris_version():
    return dict(iris_version=app.config.get('IRIS_VERSION'),
                organisation_name=app.config.get('ORGANISATION_NAME'),
                std_permissions=Permissions,
                demo_domain=app.config.get('DEMO_DOMAIN', None))


# TODO should move this method somewhere else, it is not a REST route
@app.context_processor
@cache.cached(timeout=3600, key_prefix='iris_has_updates')
def has_updates():

    return dict(has_updates=False)


def _update_user_case_ctx():
    """
    Retrieve a list of cases for the case selector
    :return:
    """
    # Get all investigations not closed
    res = Cases.query.with_entities(
        Cases.name,
        Client.name,
        Cases.case_id,
        Cases.close_date) \
        .join(Cases.client) \
        .order_by(Cases.open_date) \
        .all()

    data = [row for row in res]

    if iris_current_user and iris_current_user.ctx_case:
        # If the current user have a current case,
        # Look for it in the fresh list. If not
        # exists then remove from the user context
        is_found = False
        for row in data:
            if row[2] == iris_current_user.ctx_case:
                is_found = True
                break

        if not is_found:
            # The case does not exist,
            # Removes it from the context
            iris_current_user.ctx_case = None
            db.session.commit()

    app.jinja_env.globals.update({
        'cases_context_selector': data
    })

    return data
