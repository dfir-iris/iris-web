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
import json

from datetime import datetime

import marshmallow
from flask import Blueprint
from flask import render_template, url_for, redirect, request
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import and_, or_

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_timeline_state, update_timeline_state
from app.forms import CaseEventForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.common import parse_bf_date_format
from app.models.cases import Cases, CasesEvent
from app.models.models import CaseAssets, AssetsType, User, CaseEventsAssets, IocLink, Ioc, EventCategory
from app.schema.marshables import EventSchema
from app.util import response_success, response_error, login_required, api_login_required
from app.datamgmt.case.case_events_db import get_case_assets, get_events_categories, save_event_category, get_default_cat, \
    delete_event_category, get_case_event, update_event_assets, get_event_category, get_event_assets_ids
from app.iris_engine.utils.tracker import track_activity

import urllib.parse

event_tags = ["Network", "Server", "ActiveDirectory", "Computer", "Malware", "User Interaction"]

case_timeline_blueprint = Blueprint('case_timeline',
                                    __name__,
                                    template_folder='templates')


@case_timeline_blueprint.route('/case/timeline', methods=['GET'])
@login_required
def case_timeline(caseid, url_redir):

    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    case = Cases.query.filter(Cases.case_id == caseid).first()
    form = FlaskForm()

    return render_template("case_timeline.html", case=case, form=form)


@case_timeline_blueprint.route('/case/timeline/visualize', methods=['GET'])
@login_required
def case_getgraph_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_getgraph_page', cid=caseid, redirect=True))

    return render_template("case_graph_timeline.html")


@case_timeline_blueprint.route('/case/timeline/state', methods=['GET'])
@api_login_required
def case_get_timeline_state(caseid):
    os = get_timeline_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No timeline state for this case. Add an event to begin')


@case_timeline_blueprint.route('/case/timeline/visualize/data/by-asset', methods=['GET'])
@api_login_required
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
                tmp['date'] = row.event_date.timestamp()
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
@api_login_required
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
        ras = row

        tmp['date'] = row.event_date
        tmp['group'] = row.category[0].name
        tmp['content'] = row.event_title
        content = row.event_content.replace('\n', '<br/>')
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
@api_login_required
def case_gettimeline_api_nofilter(caseid):
    return case_gettimeline_api(0)


@case_timeline_blueprint.route('/case/timeline/events/list/filter/<int:asset_id>', methods=['GET'])
@api_login_required
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

        ras['assets'] = alki

        tim.append(ras)

    resp = {
        "timeline": tim,
        "state": get_timeline_state(caseid=caseid)
    }

    return response_success("", data=resp)


@case_timeline_blueprint.route('/case/timeline/advanced-filter', methods=['GET'])
@api_login_required
def case_filter_timeline(caseid):
    args = request.args.to_dict()
    query_filter = args.get('q')

    try:

        filter_d = dict(json.loads(urllib.parse.unquote_plus(query_filter)))

    except Exception as e:
        return response_error('Invalid query string')

    assets = filter_d.get('asset')
    tags = filter_d.get('tag')
    descriptions = filter_d.get('description')
    categories = filter_d.get('category')
    raws = filter_d.get('raw')
    start_date = filter_d.get('startDate')
    end_date = filter_d.get('endDate')
    titles = filter_d.get('title')
    sources = filter_d.get('source')

    condition = (CasesEvent.case_id == caseid)

    if assets:
        assets = [asset.lower() for asset in assets]

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

    timeline = CasesEvent.query.with_entities(
            CasesEvent.event_id,
            CasesEvent.event_date,
            CasesEvent.event_date_wtz,
            CasesEvent.event_tz,
            CasesEvent.event_title,
            CasesEvent.event_color,
            CasesEvent.event_tags,
            CasesEvent.event_content,
            CasesEvent.event_in_summary,
            CasesEvent.event_in_graph,
            EventCategory.name.label("category_name")
        ).filter(condition).order_by(
            CasesEvent.event_date
        ).outerjoin(
            CasesEvent.category
        ).all()

    assets_cache = CaseAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CaseAssets.asset_id,
        CaseAssets.asset_name,
        AssetsType.asset_name.label('type'),
        CaseAssets.asset_ip,
        CaseAssets.asset_description,
        CaseAssets.asset_compromised
    ).filter(
        CaseEventsAssets.case_id == caseid,
    ).join(CaseEventsAssets.asset, CaseAssets.asset_type).all()

    assets_map = {}
    cache = {}
    for asset in assets_cache:
        if asset.asset_id not in cache:
            cache[asset.asset_id] = [asset.asset_name, asset.type]

        if asset.asset_name.lower() in assets:
            if asset.event_id in assets_map:
                assets_map[asset.event_id] += 1
            else:
                assets_map[asset.event_id] = 1

    assets_filter = []
    for event_id in assets_map:
        if assets_map[event_id] == len(assets):
            assets_filter.append(event_id)

    tim = []
    for row in timeline:
        if assets is not None:
            if row.event_id not in assets_filter:
                continue

        ras = row._asdict()

        ras['event_date'] = ras['event_date'].strftime('%Y-%m-%dT%H:%M:%S.%f')
        ras['event_date_wtz'] = ras['event_date_wtz'].strftime('%Y-%m-%dT%H:%M:%S.%f')

        alki = []
        for asset in assets_cache:

            if asset.event_id == ras['event_id']:
                alki.append(
                    {
                        "name": "{} ({})".format(asset.asset_name, asset.type),
                        "ip": asset.asset_ip,
                        "description": asset.asset_description,
                        "compromised": asset.asset_compromised
                    }
                )

        ras['assets'] = alki

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

        resp = {
            "tim": tim,
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


@case_timeline_blueprint.route('/case/timeline/filter/<int:asset_id>', methods=['GET'])
@api_login_required
def case_gettimeline(asset_id, caseid):

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
            CasesEvent.event_date,
            CasesEvent.event_date_wtz,
            CasesEvent.event_tz,
            CasesEvent.event_title,
            CasesEvent.event_color,
            CasesEvent.event_tags,
            CasesEvent.event_content,
            CasesEvent.event_in_summary,
            CasesEvent.event_in_graph,
            EventCategory.name.label("category_name")
        ).filter(condition).order_by(
            CasesEvent.event_date
        ).outerjoin(
            CasesEvent.category
        ).all()

    assets_cache = CaseAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CaseAssets.asset_id,
        CaseAssets.asset_name,
        AssetsType.asset_name.label('type'),
        CaseAssets.asset_ip,
        CaseAssets.asset_description,
        CaseAssets.asset_compromised
    ).filter(
        CaseEventsAssets.case_id == caseid,
    ).join(CaseEventsAssets.asset, CaseAssets.asset_type).all()

    tim = []
    cache = {}
    for row in timeline:
        ras = row._asdict()
        ras['event_date'] = ras['event_date'].strftime('%Y-%m-%dT%H:%M:%S.%f')
        ras['event_date_wtz'] = ras['event_date_wtz'].strftime('%Y-%m-%dT%H:%M:%S.%f')

        alki = []
        for asset in assets_cache:
            if asset.event_id == ras['event_id']:
                if asset.asset_id not in cache:
                    cache[asset.asset_id] = [asset.asset_name, asset.type]

                alki.append(
                    {
                        "name": "{} ({})".format(asset.asset_name, asset.type),
                        "ip": asset.asset_ip,
                        "description": asset.asset_description,
                        "compromised": asset.asset_compromised
                    }
                )

        ras['assets'] = alki

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

        resp = {
            "tim": tim,
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

    return response_success("", data=resp)


@case_timeline_blueprint.route('/case/timeline/events/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def case_delete_event(cur_id, caseid):

    call_modules_hook('on_preload_event_delete', data=cur_id, caseid=caseid)

    event = get_case_event(event_id=cur_id, caseid=caseid)
    if not event:
        return response_error('Not a valid event ID for this case')

    delete_event_category(cur_id)

    CaseEventsAssets.query.filter(
        CaseEventsAssets.event_id == cur_id,
        CaseEventsAssets.case_id == caseid
    ).delete()

    db.session.commit()

    db.session.delete(event)
    update_timeline_state(caseid=caseid)

    db.session.commit()

    call_modules_hook('on_postload_event_delete', data=cur_id, caseid=caseid)

    track_activity("deleted event ID {} in timeline".format(cur_id), caseid)

    return response_success('Event ID {} deleted'.format(cur_id))


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>', methods=['GET'])
@api_login_required
def event_view(cur_id, caseid):

    event = get_case_event(cur_id, caseid)
    if not event:
        return response_error("Invalid event ID for this case")

    event_schema = EventSchema()

    linked_assets = CaseEventsAssets.query.with_entities(
        CaseEventsAssets.asset_id
    ).filter(
        CaseEventsAssets.event_id == cur_id,
        CaseEventsAssets.case_id == caseid
    ).all()

    output = event_schema.dump(event)
    output['event_assets'] = [asset[0] for asset in linked_assets]
    output['event_category_id'] = event.category[0].id

    return response_success(data=output)


@case_timeline_blueprint.route('/case/timeline/events/<int:cur_id>/modal', methods=['GET'])
@login_required
def event_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    event = get_case_event(cur_id, caseid)
    if not event:
        return response_error("Invalid event ID for this case")

    form = CaseEventForm()
    form.event_assets.choices = [("{}".format(c['asset_id']), c['asset_name']) for c in get_case_assets(caseid)]
    form.event_title.render_kw = {'value': event.event_title}
    form.event_content.data = event.event_content
    form.event_raw.data = event.event_raw
    form.event_source.render_kw = {'value': event.event_source}
    form.event_in_graph.data = event.event_in_graph
    form.event_in_summary.data = event.event_in_summary

    categories = get_events_categories()
    form.event_category_id.choices = categories

    assets_prefill = CaseEventsAssets.query.with_entities(
        CaseEventsAssets.asset_id
    ).filter(
        CaseEventsAssets.event_id == cur_id,
        CaseEventsAssets.case_id == caseid
    ).all()

    assets_prefill = [row[0] for row in assets_prefill]

    usr_name, = User.query.filter(User.id == event.user_id).with_entities(User.name).first()

    return render_template("modal_add_case_event.html", form=form, event=event, user_name=usr_name, tags=event_tags,
                           assets=get_case_assets(caseid),
                           assets_prefill=assets_prefill, category=event.category, attributes=event.custom_attributes)


@case_timeline_blueprint.route('/case/timeline/events/update/<int:cur_id>', methods=["POST"])
@api_login_required
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
        event.event_added = datetime.utcnow()
        event.user_id = current_user.id

        update_timeline_state(caseid=caseid)
        db.session.commit()

        save_event_category(event.event_id, request_data.get('event_category_id'))

        setattr(event, 'event_category_id', request_data.get('event_category_id'))

        update_event_assets(event_id=event.event_id,
                            caseid=caseid,
                            assets_list=request_data.get('event_assets'))

        event = call_modules_hook('on_postload_event_update', data=event, caseid=caseid)

        track_activity("updated event {}".format(cur_id), caseid=caseid)
        return response_success("Event added", data=event_schema.dump(event))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages(), status=400)


@case_timeline_blueprint.route('/case/timeline/events/add/modal', methods=['GET'])
@login_required
def case_add_event_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_timeline.case_timeline', cid=caseid, redirect=True))

    event = CasesEvent()
    event.custom_attributes = get_default_custom_attributes('event')
    form = CaseEventForm()
    assets = get_case_assets(caseid)
    def_cat = get_default_cat()
    categories = get_events_categories()
    form.event_category_id.choices = categories
    form.event_in_graph.data = True

    return render_template("modal_add_case_event.html", form=form, event=event,
                           tags=event_tags, assets=assets, assets_prefill=None, category=def_cat,
                           attributes=event.custom_attributes)


@case_timeline_blueprint.route('/case/timeline/events/add', methods=['POST'])
@api_login_required
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

        db.session.add(event)
        update_timeline_state(caseid=caseid)
        db.session.commit()

        save_event_category(event.event_id, request_data.get('event_category_id'))

        setattr(event, 'event_category_id', request_data.get('event_category_id'))

        update_event_assets(event_id=event.event_id,
                            caseid=caseid,
                            assets_list=request_data.get('event_assets'))

        event = call_modules_hook('on_postload_event_create', data=event, caseid=caseid)

        track_activity("added event {}".format(event.event_id), caseid=caseid)
        return response_success("Event added", data=event_schema.dump(event))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages(), status=400)


@case_timeline_blueprint.route('/case/timeline/events/duplicate/<int:cur_id>', methods=['GET'])
@api_login_required
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
            if not key.startswith('_'):
                setattr(event, key, getattr(old_event, key))

        event.event_id = orig_event_id

        # Override event_added and user_id
        event.event_added = datetime.utcnow()
        event.user_id = current_user.id
        event.event_title = f"[DUPLICATED] - {event.event_title}"
      
        db.session.add(event)
        update_timeline_state(caseid=caseid)
        db.session.commit()

        # Update category
        old_event_category = get_event_category(old_event.event_id)
        if old_event_category is not None:
            save_event_category(event.event_id, old_event_category.category_id)

        # Update assets mapping
        assets_list = get_event_assets_ids(old_event.event_id)
        update_event_assets(event_id=event.event_id,
                            caseid=caseid,
                            assets_list=assets_list)

        event = call_modules_hook('on_postload_event_create', data=event, caseid=caseid)

        track_activity("added event {}".format(event.event_id), caseid=caseid)
        return response_success("Event added", data=event_schema.dump(event))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages(), status=400)


@case_timeline_blueprint.route('/case/timeline/events/convert-date', methods=['POST'])
@api_login_required
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
