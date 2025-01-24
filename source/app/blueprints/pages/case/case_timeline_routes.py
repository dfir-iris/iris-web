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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

from app.datamgmt.case.case_events_db import get_case_assets_for_tm
from app.datamgmt.case.case_events_db import get_case_event
from app.datamgmt.case.case_events_db import get_case_events_comments_count
from app.datamgmt.case.case_events_db import get_case_iocs_for_tm
from app.datamgmt.case.case_events_db import get_default_cat
from app.datamgmt.case.case_events_db import get_event_assets_ids
from app.datamgmt.case.case_events_db import get_event_iocs_ids
from app.datamgmt.case.case_events_db import get_events_categories
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import CaseEventForm
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

_EVENT_TAGS = ['Network', 'Server', 'ActiveDirectory', 'Computer', 'Malware', 'User Interaction']

case_timeline_blueprint = Blueprint('case_timeline',
                                    __name__,
                                    template_folder='templates')


@case_timeline_blueprint.route('/case/timeline', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_timeline(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    case = Cases.query.filter(Cases.case_id == caseid).first()
    form = FlaskForm()

    return render_template("case_timeline.html", case=case, form=form)


@case_timeline_blueprint.route('/case/timeline/visualize', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_getgraph_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_getgraph_page', cid=caseid, redirect=True))

    return render_template("case_graph_timeline.html")


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    event = get_case_event(cur_id, caseid=caseid)
    if not event:
        return response_error('Invalid event ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='timeline/events',
                           title=event.event_title)


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def event_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    event = get_case_event(cur_id, caseid)
    if not event:
        return response_error("Invalid event ID for this case")

    form = CaseEventForm()
    form.event_title.render_kw = {'value': event.event_title}
    form.event_content.data = event.event_content
    form.event_raw.data = event.event_raw
    form.event_source.render_kw = {'value': event.event_source}
    form.event_in_graph.data = event.event_in_graph
    form.event_in_summary.data = event.event_in_summary

    categories = get_events_categories()
    form.event_category_id.choices = [(c.id, c.name) for c in categories]

    assets = get_case_assets_for_tm(caseid)
    iocs = get_case_iocs_for_tm(caseid)

    assets_prefill = get_event_assets_ids(cur_id, caseid)
    iocs_prefill = get_event_iocs_ids(cur_id, caseid)
    comments_map = get_case_events_comments_count([cur_id])

    usr_name, = User.query.filter(User.id == event.user_id).with_entities(User.name).first()

    return render_template("modal_add_case_event.html", form=form, event=event, user_name=usr_name, tags=_EVENT_TAGS,
                           assets=assets, iocs=iocs, comments_map=comments_map,
                           assets_prefill=assets_prefill, iocs_prefill=iocs_prefill,
                           category=event.category, attributes=event.custom_attributes)


@case_timeline_blueprint.route('/case/timeline/filter-help/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_filter_help_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    return render_template("modal_help_filter_tm.html")


@case_timeline_blueprint.route('/case/timeline/events/add/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def case_add_event_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    event = CasesEvent()
    event.custom_attributes = get_default_custom_attributes('event')
    form = CaseEventForm()
    assets = get_case_assets_for_tm(caseid)
    iocs = get_case_iocs_for_tm(caseid)
    def_cat = get_default_cat()
    categories = get_events_categories()
    form.event_category_id.choices = [(c.id, c.name) for c in categories]
    form.event_in_graph.data = True

    return render_template("modal_add_case_event.html", form=form, event=event,
                           tags=_EVENT_TAGS, assets=assets, iocs=iocs, assets_prefill=None, category=def_cat,
                           attributes=event.custom_attributes)
