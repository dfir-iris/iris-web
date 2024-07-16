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
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from sqlalchemy import and_

from app.forms import SearchForm
from app.iris_engine.access_control.utils import ac_flag_match_mask
from app.iris_engine.utils.tracker import track_activity
from app.models import Comments
from app.models.authorization import Permissions
from app.models.cases import Cases
from app.models.models import Client
from app.models.models import Ioc
from app.models.models import IocLink
from app.models.models import IocType
from app.models.models import Notes
from app.models.models import Tlp
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_success

search_blueprint = Blueprint('search',
                             __name__,
                             template_folder='templates')


@search_blueprint.route('/search', methods=['POST'])
@ac_api_requires(Permissions.search_across_cases)
def search_file_post():

    jsdata = request.get_json()
    search_value = jsdata.get('search_value')
    search_type = jsdata.get('search_type')
    files = []
    search_condition = and_()

    track_activity("started a global search for {} on {}".format(search_value, search_type))

    if search_type == "ioc":
        res = Ioc.query.with_entities(
                            Ioc.ioc_value.label('ioc_name'),
                            Ioc.ioc_description.label('ioc_description'),
                            Ioc.ioc_misp,
                            IocType.type_name,
                            Tlp.tlp_name,
                            Tlp.tlp_bscolor,
                            Cases.name.label('case_name'),
                            Cases.case_id,
                            Client.name.label('customer_name')
                    ).filter(
                        and_(
                            Ioc.ioc_value.like(search_value),
                            IocLink.ioc_id == Ioc.ioc_id,
                            IocLink.case_id == Cases.case_id,
                            Client.client_id == Cases.client_id,
                            Ioc.ioc_tlp_id == Tlp.tlp_id,
                            search_condition
                        )
                    ).join(Ioc.ioc_type).all()

        files = [row._asdict() for row in res]

    if search_type == "notes":

        ns = []
        if search_value:
            search_value = "%{}%".format(search_value)
            ns = Notes.query.filter(
                Notes.note_content.like(search_value),
                Cases.client_id == Client.client_id,
                search_condition
            ).with_entities(
                Notes.note_id,
                Notes.note_title,
                Cases.name.label('case_name'),
                Client.name.label('client_name'),
                Cases.case_id
            ).join(
                Notes.case
            ).order_by(
                Client.name
            ).all()

            ns = [row._asdict() for row in ns]

        files = ns

    if search_type == "comments":
        search_value = "%{}%".format(search_value)
        comments = Comments.query.filter(
            Comments.comment_text.like(search_value),
            Cases.client_id == Client.client_id,
            search_condition
        ).with_entities(
            Comments.comment_id,
            Comments.comment_text,
            Cases.name.label('case_name'),
            Client.name.label('customer_name'),
            Cases.case_id
        ).join(
            Comments.case
        ).join(
            Cases.client
        ).order_by(
            Client.name
        ).all()

        files = [row._asdict() for row in comments]

    return response_success("Results fetched", files)


@search_blueprint.route('/search', methods=['GET'])
@ac_requires(Permissions.search_across_cases)
def search_file_get(caseid, url_redir):
    if url_redir:
        return redirect(url_for('search.search_file_get', cid=caseid))

    form = SearchForm(request.form)
    return render_template('search.html', form=form)

