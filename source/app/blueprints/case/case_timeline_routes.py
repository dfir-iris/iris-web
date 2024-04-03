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
import csv
import json
import urllib.parse
from datetime import datetime

import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import and_

from app import db
from app import app
from app.blueprints.case.case_comments import case_comment_update
from app.datamgmt.case.case_assets_db import get_asset_by_name
from app.datamgmt.case.case_events_db import add_comment_to_event, get_category_by_name, get_default_category
from app.datamgmt.case.case_events_db import delete_event
from app.datamgmt.case.case_events_db import delete_event_comment
from app.datamgmt.case.case_events_db import get_case_assets_for_tm
from app.datamgmt.case.case_events_db import get_case_event
from app.datamgmt.case.case_events_db import get_case_event_comment
from app.datamgmt.case.case_events_db import get_case_event_comments
from app.datamgmt.case.case_events_db import get_case_events_comments_count
from app.datamgmt.case.case_events_db import get_case_iocs_for_tm
from app.datamgmt.case.case_events_db import get_default_cat
from app.datamgmt.case.case_events_db import get_event_assets_ids
from app.datamgmt.case.case_events_db import get_event_category
from app.datamgmt.case.case_events_db import get_event_iocs_ids
from app.datamgmt.case.case_events_db import get_events_categories
from app.datamgmt.case.case_events_db import save_event_category
from app.datamgmt.case.case_events_db import update_event_assets
from app.datamgmt.case.case_events_db import update_event_iocs
from app.datamgmt.case.case_iocs_db import get_ioc_by_value
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_timeline_state
from app.datamgmt.states import update_timeline_state
from app.forms import CaseEventForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.collab import collab_notify
from app.iris_engine.utils.common import parse_bf_date_format
from app.iris_engine.utils.tracker import track_activity
from app.models import CompromiseStatus
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.models import AssetsType
from app.models.models import CaseAssets
from app.models.models import CaseEventsAssets
from app.models.models import CaseEventsIoc
from app.models.models import EventCategory
from app.models.models import Ioc
from app.models.models import IocLink
from app.schema.marshables import CommentSchema
from app.schema.marshables import EventSchema
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import add_obj_history_entry
from app.util import response_error
from app.util import response_success


event_tags = ["Network", "Server", "ActiveDirectory", "Computer", "Malware", "User Interaction"]

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


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comments_get(cur_id, caseid):
    event_comments = get_case_event_comments(cur_id, caseid=caseid)
    if event_comments is None:
        return response_error('Invalid event ID')

    return response_success(data=CommentSchema(many=True).dump(event_comments))


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_delete(cur_id, com_id, caseid):
    success, msg = delete_event_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_event_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on event {cur_id} deleted", caseid=caseid)
    return response_success(msg)


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_get(cur_id, com_id, caseid):
    comment = get_case_event_comment(cur_id, com_id, caseid=caseid)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'events', caseid)


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/comments/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_add(cur_id, caseid):
    try:
        event = get_case_event(event_id=cur_id, caseid=caseid)
        if not event:
            return response_error('Invalid event ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_event(event.event_id, comment.comment_id)

        add_obj_history_entry(event, 'commented')

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "event": EventSchema().dump(event)
        }
        call_modules_hook('on_postload_event_commented', data=hook_data, caseid=caseid)

        track_activity(f"event \"{event.event_title}\" commented", caseid=caseid)
        return response_success("Event commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_timeline_blueprint.route('/case/timeline/state', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_get_timeline_state(caseid):
    os = get_timeline_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No timeline state for this case. Add an event to begin')


@case_timeline_blueprint.route('/case/timeline/visualize/data/by-asset', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_getgraph_assets(caseid):
    assets_cache = CaseAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CaseAssets.asset_name
    ).filter(
        CaseEventsAssets.case_id == caseid,
    ).join(CaseEventsAssets.asset).all()

    timeline = CasesEvent.query.filter(and_(
        CasesEvent.case_id == caseid,
        CasesEvent.event_in_summary
    )).order_by(
        CasesEvent.event_date
    ).all()

    tim = []
    for row in timeline:
        for asset in assets_cache:
            if asset.event_id == row.event_id:
                tmp = {}
                tmp['date'] = row.event_date
                tmp['group'] = asset.asset_name
                tmp['content'] = row.event_title
                tmp['title'] = f"{row.event_date.strftime('%Y-%m-%dT%H:%M:%S')} - {row.event_content}"

                if row.event_color:
                    tmp['style'] = f'background-color: {row.event_color};'

                tmp['unique_id'] = row.event_id
                tim.append(tmp)

    res = {
        "events": tim
    }

    return response_success("", data=res)


@case_timeline_blueprint.route('/case/timeline/visualize/data/by-category', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_getgraph(caseid):
    timeline = CasesEvent.query.filter(and_(
        CasesEvent.case_id == caseid,
        CasesEvent.event_in_summary
    )).order_by(
        CasesEvent.event_date
    ).all()

    tim = []
    for row in timeline:

        tmp = {}

        tmp['date'] = row.event_date
        tmp['group'] = row.category[0].name if row.category else 'Uncategorized'
        tmp['content'] = row.event_title
        if row.event_content:
            content = row.event_content.replace('\n', '<br/>')
        else:
            content = ''

        tmp['title'] = f"<small>{row.event_date.strftime('%Y-%m-%dT%H:%M:%S')}</small><br/>{content}"

        if row.event_color:
            tmp['style'] = f'background-color: {row.event_color};'

        tmp['unique_id'] = row.event_id
        tim.append(tmp)

    res = {
        "events": tim
    }

    return response_success("", data=res)


@case_timeline_blueprint.route('/case/timeline/events/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_gettimeline_api_nofilter(caseid):
    return case_gettimeline_api(0)


@case_timeline_blueprint.route('/case/timeline/events/list/filter/<int:asset_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_gettimeline_api(asset_id, caseid):
    if asset_id:
        condition = and_(
            CasesEvent.case_id == caseid,
            CaseEventsAssets.asset_id == asset_id,
            CaseEventsAssets.event_id == CasesEvent.event_id
        )
    else:
        condition = CasesEvent.case_id == caseid

    timeline = CasesEvent.query.with_entities(
        CasesEvent.event_id,
        CasesEvent.event_uuid,
        CasesEvent.event_date,
        CasesEvent.event_date_wtz,
        CasesEvent.event_tz,
        CasesEvent.event_title,
        CasesEvent.event_color,
        CasesEvent.event_tags,
        CasesEvent.event_content,
        CasesEvent.event_in_summary,
        CasesEvent.event_in_graph,
        EventCategory.name.label("category_name"),
        EventCategory.id.label("event_category_id")
    ).filter(condition).order_by(
        CasesEvent.event_date
    ).outerjoin(
        CasesEvent.category
    ).all()

    assets_cache = CaseAssets.query.with_entities(
        CaseAssets.asset_id,
        CaseAssets.asset_name,
        CaseEventsAssets.event_id
    ).filter(
        CaseEventsAssets.case_id == caseid,
    ).join(CaseEventsAssets.asset).all()

    iocs_cache = CaseEventsIoc.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_value,
        CaseEventsIoc.event_id
    ).filter(
        CaseEventsIoc.case_id == caseid
    ).join(
        CaseEventsIoc.ioc
    ).all()

    tim = []
    for row in timeline:
        ras = row._asdict()
        ras['event_date'] = ras['event_date'].strftime('%Y-%m-%dT%H:%M:%S.%f')
        ras['event_date_wtz'] = ras['event_date_wtz'].strftime('%Y-%m-%dT%H:%M:%S.%f')

        alki = []
        cache = {}
        for asset in assets_cache:
            if asset.event_id == ras['event_id']:
                if asset.asset_id not in cache:
                    cache[asset.asset_id] = asset.asset_name

                alki.append(asset._asdict())

        alki = []
        cache = {}
        for ioc in iocs_cache:
            if ioc.event_id == ras['event_id']:
                if ioc.ioc_id not in cache:
                    cache[ioc.ioc_id] = ioc.ioc_value

                alki.append(ioc._asdict())

        ras['iocs'] = alki

        tim.append(ras)

    resp = {
        "timeline": tim,
        "state": get_timeline_state(caseid=caseid)
    }

    return response_success("", data=resp)


@case_timeline_blueprint.route('/case/timeline/advanced-filter', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_filter_timeline(caseid):
    args = request.args.to_dict()
    query_filter = args.get('q')

    try:

        filter_d = dict(json.loads(urllib.parse.unquote_plus(query_filter)))

    except Exception as e:
        return response_error('Invalid query string')

    assets = filter_d.get('asset')
    assets_id = filter_d.get('asset_id')
    event_ids = filter_d.get('event_id')
    iocs = filter_d.get('ioc')
    iocs_id = filter_d.get('ioc_id')
    tags = filter_d.get('tag')
    descriptions = filter_d.get('description')
    categories = filter_d.get('category')
    raws = filter_d.get('raw')
    start_date = filter_d.get('startDate')
    end_date = filter_d.get('endDate')
    titles = filter_d.get('title')
    sources = filter_d.get('source')
    flag = filter_d.get('flag')

    condition = (CasesEvent.case_id == caseid)

    if assets:
        assets = [asset.lower() for asset in assets]

    if assets_id:
        assets_id = [int(asset) for asset in assets_id]

    if flag:
        flags = (flag[0].lower() == 'true')
        condition = and_(condition, CasesEvent.event_is_flagged == flags)

    if iocs:
        iocs = [ioc.lower() for ioc in iocs]

    if iocs_id:
        iocs_id = [int(ioc) for ioc in iocs_id]

    if tags:
        for tag in tags:
            condition = and_(condition,
                             CasesEvent.event_tags.ilike(f'%{tag}%'))

    if titles:
        for title in titles:
            condition = and_(condition,
                             CasesEvent.event_title.ilike(f'%{title}%'))

    if sources:
        for source in sources:
            condition = and_(condition,
                             CasesEvent.event_source.ilike(f'%{source}%'))

    if descriptions:
        for description in descriptions:
            condition = and_(condition,
                             CasesEvent.event_content.ilike(f'%{description}%'))

    if raws:
        for raw in raws:
            condition = and_(condition,
                             CasesEvent.event_raw.ilike(f'%{raw}%'))

    if start_date:
        try:
            parsed_start_date = parse_bf_date_format(start_date[0])
            condition = and_(condition,
                             CasesEvent.event_date >= parsed_start_date)

        except Exception as e:
            print(e)
            pass

    if end_date:
        try:
            parsed_end_date = parse_bf_date_format(end_date[0])
            condition = and_(condition,
                             CasesEvent.event_date <= parsed_end_date)
        except Exception as e:
            pass

    if categories:
        for category in categories:
            condition = and_(condition,
                             EventCategory.name == category)

    if event_ids:
        try:
            event_ids = [int(event_id) for event_id in event_ids]
        except Exception as e:
            return response_error('Invalid event id')

        condition = and_(condition,
                         CasesEvent.event_id.in_(event_ids))

    timeline = CasesEvent.query.with_entities(
        CasesEvent.event_id,
        CasesEvent.event_uuid,
        CasesEvent.event_date,
        CasesEvent.event_date_wtz,
        CasesEvent.event_tz,
        CasesEvent.event_title,
        CasesEvent.event_color,
        CasesEvent.event_tags,
        CasesEvent.event_content,
        CasesEvent.event_in_summary,
        CasesEvent.event_in_graph,
        CasesEvent.event_is_flagged,
        CasesEvent.parent_event_id,
        User.user,
        CasesEvent.event_added,
        EventCategory.name.label("category_name")
    ).filter(condition).order_by(
        CasesEvent.event_date
    ).outerjoin(
        CasesEvent.category
    ).join(
        CasesEvent.user
    ).all()

    assets_cache_condition = and_(
        CaseEventsAssets.case_id == caseid
    )

    if assets_id:
        assets_cache_condition = and_(
            assets_cache_condition,
            CaseEventsAssets.asset_id.in_(assets_id)
        )

    assets_cache = (CaseAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CaseAssets.asset_id,
        CaseAssets.asset_name,
        AssetsType.asset_name.label('type'),
        CaseAssets.asset_ip,
        CaseAssets.asset_description,
        CaseAssets.asset_compromise_status_id
    ).filter(
        assets_cache_condition
    ).join(CaseEventsAssets.asset)
     .join(CaseAssets.asset_type).all())

    iocs_cache_condition = and_(
        CaseEventsIoc.case_id == caseid
    )

    if iocs_id:
        iocs_cache_condition = and_(
            iocs_cache_condition,
            CaseEventsIoc.ioc_id.in_(iocs_id)
        )

    iocs_cache = CaseEventsIoc.query.with_entities(
        CaseEventsIoc.event_id,
        CaseEventsIoc.ioc_id,
        Ioc.ioc_value,
        Ioc.ioc_description
    ).filter(
        iocs_cache_condition
    ).join(
        CaseEventsIoc.ioc
    ).all()

    assets_map = {}
    cache = {}
    for asset in assets_cache:
        if asset.asset_id not in cache:
            cache[asset.asset_id] = [asset.asset_name, asset.type]

        if (assets and asset.asset_name.lower() in assets) \
                or (assets_id and asset.asset_id in assets_id):
            if asset.event_id in assets_map:
                assets_map[asset.event_id] += 1
            else:
                assets_map[asset.event_id] = 1

    assets_filter = []
    len_assets = 0
    if assets:
        len_assets += len(assets)
    if assets_id:
        len_assets += len(assets_id)

    for event_id in assets_map:
        if assets_map[event_id] == len_assets:
            assets_filter.append(event_id)

    iocs_filter = []
    if iocs:
        for ioc in iocs_cache:
            if ioc.event_id not in iocs_filter and ioc.ioc_value.lower() in iocs:
                iocs_filter.append(ioc.event_id)

    tim = []
    events_list = []
    for row in timeline:
        if assets is not None or assets_id is not None:
            if row.event_id not in assets_filter:
                continue

        if iocs is not None:
            if row.event_id not in iocs_filter:
                continue

        ras = row._asdict()

        ras['event_date'] = ras['event_date'].strftime('%Y-%m-%dT%H:%M:%S.%f')
        ras['event_date_wtz'] = ras['event_date_wtz'].strftime('%Y-%m-%dT%H:%M:%S.%f') if ras[
            'event_date_wtz'] else None
        ras['event_added'] = ras['event_added'].strftime('%Y-%m-%dT%H:%M:%S')

        if row.event_id not in events_list:
            events_list.append(row.event_id)

        alki = []
        for asset in assets_cache:

            if asset.event_id == ras['event_id']:
                alki.append(
                    {
                        "name": "{} ({})".format(asset.asset_name, asset.type),
                        "ip": asset.asset_ip,
                        "description": asset.asset_description,
                        "compromised": asset.asset_compromise_status_id == CompromiseStatus.compromised.value
                    }
                )

        ras['assets'] = alki

        alki = []
        for ioc in iocs_cache:
            if ioc.event_id == ras['event_id']:
                if ioc.ioc_id not in cache:
                    cache[ioc.ioc_id] = [ioc.ioc_value]

                alki.append(
                    {
                        "name": "{}".format(ioc.ioc_value),
                        "description": ioc.ioc_description
                    }
                )

        ras['iocs'] = alki

        tim.append(ras)

    if request.cookies.get('session'):

        iocs = IocLink.query.with_entities(
            Ioc.ioc_id,
            Ioc.ioc_value,
            Ioc.ioc_description,
        ).filter(
            IocLink.case_id == caseid,
            Ioc.ioc_id == IocLink.ioc_id
        ).all()

        events_comments_map = {}
        events_comments_set = get_case_events_comments_count(events_list)
        for k, v in events_comments_set:
            events_comments_map.setdefault(k, []).append(v)

        resp = {
            "tim": tim,
            "comments_map": events_comments_map,
            "assets": cache,
            "iocs": [ioc._asdict() for ioc in iocs],
            "categories": [cat.name for cat in get_events_categories()],
            "state": get_timeline_state(caseid=caseid)
        }

    else:
        resp = {
            "timeline": tim,
            "state": get_timeline_state(caseid=caseid)
        }

    return response_success("ok", data=resp)


@case_timeline_blueprint.route('/case/timeline/events/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_delete_event(cur_id, caseid):
    call_modules_hook('on_preload_event_delete', data=cur_id, caseid=caseid)

    event = get_case_event(event_id=cur_id, caseid=caseid)
    if not event:
        return response_error('Not a valid event ID for this case')

    delete_event(event=event, caseid=caseid)

    call_modules_hook('on_postload_event_delete', data=cur_id, caseid=caseid)

    collab_notify(caseid, 'events', 'deletion', cur_id)

    track_activity(f"deleted event \"{event.event_title}\" in timeline", caseid)

    return response_success('Event ID {} deleted'.format(cur_id))


@case_timeline_blueprint.route('/case/timeline/events/flag/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def event_flag(cur_id, caseid):
    event = get_case_event(cur_id, caseid)
    if not event:
        return response_error("Invalid event ID for this case")

    event.event_is_flagged = not event.event_is_flagged
    db.session.commit()

    collab_notify(caseid, 'events', 'flagged' if event.event_is_flagged else "un-flagged", cur_id)

    return response_success("Event flagged" if event.event_is_flagged else "Event unflagged", data=event)


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def event_view(cur_id, caseid):
    event = get_case_event(cur_id, caseid)
    if not event:
        return response_error("Invalid event ID for this case")

    event_schema = EventSchema()

    linked_assets = get_event_assets_ids(cur_id, caseid)
    linked_iocs = get_event_iocs_ids(cur_id, caseid)

    output = event_schema.dump(event)
    output['event_assets'] = linked_assets
    output['event_iocs'] = linked_iocs
    output['event_category_id'] = event.category[0].id if event.category else None
    output['event_comments_map'] = [c._asdict() for c in get_case_events_comments_count([cur_id])]

    return response_success(data=output)


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
    form.event_category_id.choices = categories

    assets = get_case_assets_for_tm(caseid)
    iocs = get_case_iocs_for_tm(caseid)

    assets_prefill = get_event_assets_ids(cur_id, caseid)
    iocs_prefill = get_event_iocs_ids(cur_id, caseid)
    comments_map = get_case_events_comments_count([cur_id])

    usr_name, = User.query.filter(User.id == event.user_id).with_entities(User.name).first()

    return render_template("modal_add_case_event.html", form=form, event=event, user_name=usr_name, tags=event_tags,
                           assets=assets, iocs=iocs, comments_map=comments_map,
                           assets_prefill=assets_prefill, iocs_prefill=iocs_prefill,
                           category=event.category, attributes=event.custom_attributes)


@case_timeline_blueprint.route('/case/timeline/events/update/<int:cur_id>', methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_edit_event(cur_id, caseid):
    try:
        event = get_case_event(cur_id, caseid)
        if not event:
            return response_error("Invalid event ID for this case")

        event_schema = EventSchema()

        request_data = call_modules_hook('on_preload_event_update', data=request.get_json(), caseid=caseid)

        request_data['event_id'] = cur_id
        event = event_schema.load(request_data, instance=event)

        event.event_date, event.event_date_wtz = event_schema.validate_date(
            request_data.get(u'event_date'),
            request_data.get(u'event_tz')
        )

        event.case_id = caseid
        add_obj_history_entry(event, 'updated')

        update_timeline_state(caseid=caseid)
        db.session.commit()

        save_event_category(event.event_id, request_data.get('event_category_id'))

        setattr(event, 'event_category_id', request_data.get('event_category_id'))

        success, log = update_event_assets(event_id=event.event_id,
                                           caseid=caseid,
                                           assets_list=request_data.get('event_assets'),
                                           iocs_list=request_data.get('event_iocs'),
                                           sync_iocs_assets=request_data.get('event_sync_iocs_assets'))
        if not success:
            return response_error('Error while saving linked assets', data=log)

        success, log = update_event_iocs(event_id=event.event_id,
                                         caseid=caseid,
                                         iocs_list=request_data.get('event_iocs'))
        if not success:
            return response_error('Error while saving linked iocs', data=log)

        event = call_modules_hook('on_postload_event_update', data=event, caseid=caseid)

        track_activity(f"updated event \"{event.event_title}\"", caseid=caseid)
        event_dump = event_schema.dump(event)
        collab_notify(case_id=caseid,
                      object_type='events',
                      action_type='updated',
                      object_id=cur_id,
                      object_data=event_dump)

        return response_success("Event updated", data=event_dump)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_timeline_blueprint.route('/case/timeline/events/add/modal', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_event_modal(caseid):
    event = CasesEvent()
    event.custom_attributes = get_default_custom_attributes('event')
    form = CaseEventForm()
    assets = get_case_assets_for_tm(caseid)
    iocs = get_case_iocs_for_tm(caseid)
    def_cat = get_default_cat()
    categories = get_events_categories()
    form.event_category_id.choices = categories
    form.event_in_graph.data = True

    return render_template("modal_add_case_event.html", form=form, event=event,
                           tags=event_tags, assets=assets, iocs=iocs, assets_prefill=None, category=def_cat,
                           attributes=event.custom_attributes)


@case_timeline_blueprint.route('/case/timeline/filter-help/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_filter_help_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    return render_template("modal_help_filter_tm.html")


@case_timeline_blueprint.route('/case/timeline/events/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_event(caseid):
    try:

        event_schema = EventSchema()
        request_data = call_modules_hook('on_preload_event_create', data=request.get_json(), caseid=caseid)

        event = event_schema.load(request_data)

        event.event_date, event.event_date_wtz = event_schema.validate_date(request_data.get(u'event_date'),
                                                                            request_data.get(u'event_tz'))

        event.case_id = caseid
        event.event_added = datetime.utcnow()
        event.user_id = current_user.id

        add_obj_history_entry(event, 'created')

        db.session.add(event)
        update_timeline_state(caseid=caseid)
        db.session.commit()

        save_event_category(event.event_id, request_data.get('event_category_id'))

        setattr(event, 'event_category_id', request_data.get('event_category_id'))
        sync_iocs_assets = request_data.get('event_sync_iocs_assets') if request_data.get(
            'event_sync_iocs_assets') else False

        success, log = update_event_assets(event_id=event.event_id,
                                           caseid=caseid,
                                           assets_list=request_data.get('event_assets'),
                                           iocs_list=request_data.get('event_iocs'),
                                           sync_iocs_assets=sync_iocs_assets)
        if not success:
            return response_error('Error while saving linked assets', data=log)

        success, log = update_event_iocs(event_id=event.event_id,
                                         caseid=caseid,
                                         iocs_list=request_data.get('event_iocs'))
        if not success:
            return response_error('Error while saving linked iocs', data=log)

        setattr(event, 'event_category_id', request_data.get('event_category_id'))

        event = call_modules_hook('on_postload_event_create', data=event, caseid=caseid)

        track_activity(f"added event \"{event.event_title}\"", caseid=caseid)
        return response_success("Event added", data=event_schema.dump(event))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_timeline_blueprint.route('/case/timeline/events/duplicate/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_duplicate_event(cur_id, caseid):
    call_modules_hook('on_preload_event_duplicate', data=cur_id, caseid=caseid)

    try:
        event_schema = EventSchema()
        old_event = get_case_event(event_id=cur_id, caseid=caseid)
        if not old_event:
            return response_error("Invalid event ID for this case")

        # Create new Event
        event = CasesEvent()
        orig_event_id = event.event_id
        # Transfer duplicated event's attributes to new event
        for key in dir(old_event):
            if not key.startswith('_') and key not in ['query', 'query_class', 'registry', 'metadata']:
                setattr(event, key, getattr(old_event, key))

        event.event_id = orig_event_id

        # Override event_added and user_id
        event.event_added = datetime.utcnow()
        event.user_id = current_user.id
        if event.event_title.startswith("[DUPLICATED] - ") is False:
            event.event_title = f"[DUPLICATED] - {event.event_title}"

        db.session.add(event)
        update_timeline_state(caseid=caseid)
        db.session.commit()

        # Update category
        old_event_category = get_event_category(old_event.event_id)
        if old_event_category is not None:
            save_event_category(event.event_id, old_event_category.category_id)

        iocs_list = get_event_iocs_ids(old_event.event_id, caseid)
        # Update assets mapping
        assets_list = get_event_assets_ids(old_event.event_id, caseid)
        success, log = update_event_assets(event_id=event.event_id,
                                           caseid=caseid,
                                           assets_list=assets_list,
                                           iocs_list=iocs_list,
                                           sync_iocs_assets=False)
        if not success:
            return response_error('Error while saving linked assets', data=log)

        # Update iocs mapping
        success, log = update_event_iocs(event_id=event.event_id,
                                         caseid=caseid,
                                         iocs_list=iocs_list)
        if not success:
            return response_error('Error while saving linked iocs', data=log)

        event = call_modules_hook('on_postload_event_create', data=event, caseid=caseid)

        track_activity(f"added event \"{event.event_title}\"", caseid=caseid)
        return response_success("Event duplicated", data=event_schema.dump(event))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_timeline_blueprint.route('/case/timeline/events/convert-date', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_event_date_convert(caseid):
    jsdata = request.get_json()

    date_value = jsdata.get('date_value')
    if not date_value:
        return response_error("Invalid request")

    parsed_date = parse_bf_date_format(date_value)

    if parsed_date:
        tz = parsed_date.strftime("%z")
        data = {
            "date": parsed_date.strftime("%Y-%m-%d"),
            "time": parsed_date.strftime("%H:%M:%S.%f")[:-3],
            "tz": tz if tz else "+00:00"
        }
        return response_success("Date parsed", data=data)

    return response_error("Unable to find a matching date format")


# BEGIN_RS_CODE
@case_timeline_blueprint.route('/case/timeline/events/csv_upload', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_events_upload_csv(caseid):
    event_schema = EventSchema()

    jsdata = request.get_json()
    app.logger.info("Starting CSV import")
    event_fields = [
        "event_date",
        "event_tz",
        "event_title",
        "event_category",
        "event_content",
        "event_raw",
        "event_source",
        "event_assets",
        "event_iocs",
        "event_tags"
    ]

    csv_lines = jsdata["CSVData"].splitlines()

    csv_options = jsdata.get('CSVOptions') if jsdata.get('CSVOptions') else {}

    event_sync_iocs_assets = csv_options.get('event_sync_iocs_assets') if csv_options.get(
        'event_sync_iocs_assets') else False
    event_in_summary = csv_options.get('event_in_summary') if csv_options.get('event_in_summary') else False
    event_in_graph = csv_options.get('event_in_graph') if csv_options.get('event_in_graph') else True
    event_source = csv_options.get('event_source') if csv_options.get('event_source') else ''

    csv_data = list(csv.DictReader(csv_lines, delimiter=','))
    missing_fields = []
    row0 = csv_data[0]
    for fld in event_fields:
        if row0.get(fld) is None:
            missing_fields.append(fld)

    if len(missing_fields) > 0:
        csv_fields = list(row0.keys())
        msg = f"Bad SCV Fields Mapping. Fields missing: [{','.join(missing_fields)}]"
        data = {"error_code": "BAD_FIELDS_MAPPING", "expected": ','.join(event_fields), "found": ','.join(csv_fields),
                "missing": ','.join(missing_fields)}
        app.logger.warning(data)

        return response_error(msg=msg, data=data)

    DEFAULT_CAT_ID = get_default_category().id

    # ==========================  checking data validity (assets, ioc, categories, etc... )  ==========================
    line = 0
    csv_lines = []
    try:

        for row in csv_data:
            event_title = row.get('event_title')
            event_assets = row.get('event_assets')
            event_iocs = row.get('event_iocs')
            event_tags = row.get('event_tags')
            event_category_name = row.pop('event_category')

            line += 1

            if len(event_title) == 0:
                return response_error(msg=f"Data error",
                                      data={"Error": f"Event Title can not be empty.\nrow number: {line}"})

            assets = []
            for asset_name in event_assets.split(";"):
                if asset_name == '':
                    continue
                asset = get_asset_by_name(asset_name, caseid)
                if asset:
                    assets.append(asset.asset_id)
                else:
                    return response_error(msg=f"Data error", data={
                        "Error": f"Asset not recognized : {asset_name}.\nrow number: {line}"})

            row['event_assets'] = assets

            iocs = []
            for ioc_value in event_iocs.split("|"):
                if ioc_value == '':
                    continue
                ioc = get_ioc_by_value(ioc_value, caseid)
                if ioc:
                    iocs.append(ioc.ioc_id)
                else:
                    return response_error(msg=f"Data error",
                                          data={"Error": f"IoC not recognized : {ioc_value}.\nrow number: {line}"})
            row['event_iocs'] = iocs

            if (event_category_name is not None) and (event_category_name != ''):
                event_category = get_category_by_name(event_category_name)
                if event_category:
                    row['event_category_id'] = event_category.id
                else:
                    return response_error(msg=f"Data error", data={
                        "Error": f"event_category not recognized : {event_category}.\nrow number: {line}"})
            else:
                row['event_category_id'] = DEFAULT_CAT_ID

            if event_tags:
                row['event_tags'] = ','.join(event_tags.split('|'))

            row['event_in_summary'] = event_in_summary
            row['event_in_graph'] = event_in_graph
            row['event_source'] = event_source

            csv_lines.append(row)
    except Exception as e:
        return response_error(msg=f"Data error", data={"Exception": f"Unhandled error {e}.\nrow number: {line}"})

    # ========================== begin saving data ============================
    session = db.session.begin_nested()
    line = 0
    try:
        for row in csv_lines:
            if row is None:
                continue
            line += 1

            request_data = call_modules_hook('on_preload_event_create', data=row, caseid=caseid)
            event = event_schema.load(request_data)
            event.event_date, event.event_date_wtz = event_schema.validate_date(request_data.get(u'event_date'),
                                                                                request_data.get(u'event_tz'))
            event.case_id = caseid
            event.event_added = datetime.utcnow()
            event.user_id = current_user.id

            add_obj_history_entry(event, 'created')

            db.session.add(event)
            update_timeline_state(caseid=caseid)

            save_event_category(event.event_id, request_data.get('event_category_id'))

            setattr(event, 'event_category_id', request_data.get('event_category_id'))

            success, log = update_event_assets(event_id=event.event_id,
                                               caseid=caseid,
                                               assets_list=request_data.get('event_assets'),
                                               iocs_list=request_data.get('event_iocs'),
                                               sync_iocs_assets=event_sync_iocs_assets)
            if not success:
                raise Exception(f'Error while saving linked assets\nlog:{log}')

            success, log = update_event_iocs(event_id=event.event_id,
                                             caseid=caseid,
                                             iocs_list=request_data.get('event_iocs'))
            if not success:
                raise Exception(f'Error while saving linked iocs\nlog:{log}')

            setattr(event, 'event_category_id', request_data.get('event_category_id'))

            event = call_modules_hook('on_postload_event_create', data=event, caseid=caseid)

            track_activity("added event {}".format(event.event_id), caseid=caseid)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())

    except Exception as e:
        return response_error(msg=f"Data error", data={"Error": f"{e}"})

    # db.session.commit()
    try:
        session.commit()
    except:
        pass

    app.logger.info("======================== END_CSV_IMPORT ==========================================")

    return response_success(msg="Events added (CSV File)")

# END_RS_CODE
