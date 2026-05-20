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
import datetime
import decimal
import json
import pickle
import uuid

from flask import render_template
from flask import request
from sqlalchemy.orm import DeclarativeMeta

from app import TEMPLATE_PATH
from app import app


# Set basic 404
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    if request.content_type and 'application/json' in request.content_type:
        return response_error("Resource not found", status=404)

    return render_template('pages/error-404.html', template_folder=TEMPLATE_PATH), 404


def response(status, data=None):
    if data is not None:
        data = json.dumps(data, cls=AlchemyEncoder)
    return app.response_class(response=data, status=status, mimetype='application/json')


def response_error(msg, data=None, status=400):
    content = {
        'status': 'error',
        'message': msg,
        'data': data if data is not None else []
    }
    return response(status, data=content)


def response_success(msg='', data=None):
    content = {
        "status": "success",
        "message": msg,
        "data": data if data is not None else []
    }
    return response(200, data=content)


class AlchemyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata'
                                                 and x != 'query' and x != 'query_class']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data)  # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        if isinstance(obj, decimal.Decimal):
            return str(obj)

        if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
            return obj.isoformat()

        if isinstance(obj, uuid.UUID):
            return str(obj)

        if obj.__class__ == bytes:
            try:
                return pickle.load(obj)
            except Exception:
                return str(obj)

        return json.JSONEncoder.default(self, obj)
