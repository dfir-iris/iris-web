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
from flask import Blueprint
from flask import render_template, request, url_for, redirect
from sqlalchemy import and_, or_
import json

from app import db
from app.forms import SearchForm

from app.models.models import HashLink, FileName, PathName, CasesDatum, FileContentHash, Ioc, IocLink, Client, Tlp, \
    Notes
from app.models.cases import Cases

from app.iris_engine.utils.tracker import track_activity

from app.util import response_success, response_error, AlchemyFnCode, get_urlcase, login_required

search_blueprint = Blueprint('search',
                             __name__,
                             template_folder='templates')


# CONTENT ------------------------------------------------
@search_blueprint.route('/search', methods=['GET', 'POST'])
@login_required
def search_file(caseid: int,  url_redir):
    if url_redir:
        return redirect(url_for('search.search_file', cid=caseid))

    form = SearchForm(request.form)

    if form.validate_on_submit():

        search_value = request.form.get('search_value', '', type=str)
        search_type = request.form.get('search_type', '', type=str)
        files = []

        track_activity("started a search for {} on {}".format(search_value, search_type))

        if search_type == "files":
            select = db.select([FileContentHash.content_hash.label('content_hash'),
                                FileContentHash.vt_score.label('vt_score'),
                                FileContentHash.vt_url.label('vt_url'),
                                FileContentHash.comment.label('comment'),
                                FileContentHash.flag.label('flag'),
                                FileName.filename.label('filename'),
                                PathName.path.label('path'),
                                FileContentHash.seen_count.label('seen_count'),
                                Cases.name.label('case_name')
                                ]).distinct().where(
                                    and_(
                                        FileContentHash.content_hash == HashLink.content_hash,
                                        HashLink.fn_hash == FileName.fn_hash,
                                        FileName.filename.like(search_value),
                                        HashLink.path_hash == PathName.path_hash,
                                        CasesDatum.link_key == HashLink.link_key,
                                        Cases.case_id == CasesDatum.case_id
                                        )
                                )
            res = db.engine.execute(select)
            files = json.dumps([dict(row) for row in res.fetchall()], default=AlchemyFnCode)

        if search_type == "hashes":
            select = db.select([FileContentHash.content_hash.label('content_hash'),
                                FileContentHash.vt_score.label('vt_score'),
                                FileContentHash.vt_url.label('vt_url'),
                                FileContentHash.comment.label('comment'),
                                FileContentHash.flag.label('flag'),
                                FileName.filename.label('filename'),
                                PathName.path.label('path'),
                                FileContentHash.seen_count.label('seen_count'),
                                Cases.name.label('case_name')
                                ]).distinct().where(
                                    and_(
                                        FileContentHash.content_hash == search_value,
                                        FileContentHash.content_hash == HashLink.content_hash,
                                        HashLink.fn_hash == FileName.fn_hash,
                                        HashLink.path_hash == PathName.path_hash,
                                        CasesDatum.link_key == HashLink.link_key,
                                        Cases.case_id == CasesDatum.case_id
                                        )
                                )

            try:
                res = db.engine.execute(select)
                files = json.dumps([dict(row) for row in res.fetchall()], default=AlchemyFnCode)
            except Exception as e:
                return response_error("Invalid query", files)

        if search_type == "ioc":
            res = Ioc.query.with_entities(
                                Ioc.ioc_value.label('ioc_name'),
                                Ioc.ioc_description.label('ioc_description'),
                                Ioc.ioc_misp,
                                Ioc.ioc_type,
                                Tlp.tlp_name,
                                Tlp.tlp_bscolor,
                                Cases.name.label('case_name'),
                                Client.name.label('customer_name')
                        ).filter(
                            and_(
                                Ioc.ioc_value.like(search_value),
                                IocLink.ioc_id == Ioc.ioc_id,
                                IocLink.case_id == Cases.case_id,
                                Client.client_id == Cases.client_id,
                                Ioc.ioc_tlp_id == Tlp.tlp_id
                            )
                        ).all()

            files = [row._asdict() for row in res]

        if search_type == "notes":

            ns = []
            if search_value:
                search_value = "%{}%".format(search_value)
                ns = Notes.query.filter(
                    Notes.note_content.like(search_value),
                    Cases.client_id == Client.client_id
                ).with_entities(
                    Notes.note_id,
                    Notes.note_title,
                    Cases.name,
                    Client.name
                ).join(
                    Notes.case
                ).order_by(
                    Client.name
                ).all()

                ns = [row for row in ns]

            files = ns

        return response_success("Results fetched", files)

    elif request.method == 'POST':
        return response_error("Failure", form.errors)

    return render_template('search.html', form=form)