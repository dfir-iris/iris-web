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

import itertools
from datetime import datetime
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_events_db import get_case_events_assets_graph
from app.datamgmt.case.case_events_db import get_case_events_ioc_graph
from app.models.authorization import CaseAccessLevel
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import response_success

case_graph_blueprint = Blueprint('case_graph',
                                 __name__,
                                 template_folder='templates')


# CONTENT ------------------------------------------------
@case_graph_blueprint.route('/case/graph', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_graph(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_graph.case_graph', cid=caseid, redirect=True))

    case = get_case(caseid)
    form = FlaskForm()

    return render_template("case_graph.html", case=case, form=form)


@case_graph_blueprint.route('/case/graph/getdata', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_graph_get_data(caseid):
    events = get_case_events_assets_graph(caseid)
    events.extend(get_case_events_ioc_graph(caseid))

    nodes = []
    edges = []
    dates = {
        "human": [],
        "machine": []
    }

    tmp = {}
    for event in events:
        if hasattr(event, 'asset_compromise_status_id'):
            if event.asset_compromise_status_id == 1:
                img = event.asset_icon_compromised

            else:
                img = event.asset_icon_not_compromised

            if event.asset_ip:
                title = "{} -{}".format(event.asset_ip, event.asset_description)
            else:
                title = "{}".format(event.asset_description)
            label = event.asset_name
            idx = f'a{event.asset_id}'
            node_type = 'asset'

        else:
            img = 'virus-covid-solid.png'
            label = event.ioc_value
            title = event.ioc_description
            idx = f'b{event.ioc_id}'
            node_type = 'ioc'

        try:
            date = "{}-{}-{}".format(event.event_date.day, event.event_date.month, event.event_date.year)
        except:
            date = '15-05-2021'

        if date not in dates:
            dates['human'].append(date)
            dates['machine'].append(datetime.timestamp(event.event_date))

        new_node = {
            'id': idx,
            'label': label,
            'image': '/static/assets/img/graph/' + img,
            'shape': 'image',
            'title': title,
            'value': 1
        }

        if current_user.in_dark_mode:
            new_node['font'] = "12px verdana white"

        if not any(node['id'] == idx for node in nodes):
            nodes.append(new_node)

        ak = {
            'node_id': idx,
            'node_title': "{} - {}".format(event.event_date, event.event_title),
            'node_name': label,
            'node_type': node_type
        }
        if tmp.get(event.event_id):
            tmp[event.event_id]['list'].append(ak)

        else:
            tmp[event.event_id] = {
                'master_node':  [],
                'list': [ak]
            }

    for event_id in tmp:
        for subset in itertools.combinations(tmp[event_id]['list'], 2):

            if subset[0]['node_type'] == 'ioc' and subset[1]['node_type'] == 'ioc' and len(tmp[event_id]['list']) != 2:
                continue
                
            edge = {
                'from': subset[0]['node_id'],
                'to': subset[1]['node_id'],
                'title': subset[0]['node_title'],
                'dashes': subset[0]['node_type'] == 'ioc' or subset[1]['node_type'] == 'ioc'
            }
            edges.append(edge)

    resp = {
        'nodes': nodes,
        'edges': edges,
        'dates': dates
    }

    return response_success("", data=resp)
