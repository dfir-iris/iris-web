#  IRIS Source Code
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
import json
from flask import Blueprint
from flask import request
from werkzeug import Response

from app import app
from app.datamgmt.manage.manage_tags_db import get_filtered_tags
from app.schema.marshables import TagsSchema
from app.util import ac_api_requires
from app.util import AlchemyEncoder
from app.util import response_success

manage_tags_blueprint = Blueprint('manage_tags',
                                  __name__,
                                  template_folder='templates')


@manage_tags_blueprint.route('/manage/tags/filter', methods=['GET'])
@ac_api_requires()
def manage_tags_filter() -> Response:
    """ Returns a list of tags, filtered by the given parameters.

    :param caseid: Case ID - Unused
    :return: Response

    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    order_by = request.args.get('order_by', 'name', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)

    tag_title = request.args.get('tag_title', None, type=str)
    if tag_title is None:
        tag_title = request.args.get('term', None, type=str)
    tag_namespace = request.args.get('tag_namespace', None, type=str)

    draw = request.args.get('draw', 1, type=int)

    if type(draw) is not int:
        draw = 1

    filtered_tags = get_filtered_tags(tag_title=tag_title,
                                      tag_namespace=tag_namespace,
                                      page=page,
                                      per_page=per_page,
                                      sort_by=order_by,
                                      sort_dir=sort_dir)

    tags = {
        'total': filtered_tags.total,
        'tags': TagsSchema().dump(filtered_tags.items, many=True),
        'last_page': filtered_tags.pages,
        'current_page': filtered_tags.page,
        'next_page': filtered_tags.next_num if filtered_tags.has_next else None,
        'draw': draw
    }

    return response_success('', data=tags)


@manage_tags_blueprint.route('/manage/tags/suggest', methods=['GET'])
@ac_api_requires()
def manage_tags_suggest() -> Response:
    tag_title = request.args.get('term', None, type=str)
    filtered_tags = get_filtered_tags(tag_title=tag_title,
                                      tag_namespace=None,
                                      page=1,
                                      per_page=15,
                                      sort_by='tage_title',
                                      sort_dir='asc')

    tags = {
        "suggestions": [tag.tag_title for tag in filtered_tags.items]
    }

    return app.response_class(response=json.dumps(tags, cls=AlchemyEncoder),
                              status=200,
                              mimetype='application/json')
