#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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

import urllib.parse
import json
import datetime


def _unquote(u):
    return urllib.parse.unquote(u)


def _to_json_safe(u):
    return json.dumps(u, indent=4, ensure_ascii=False)


def _to_json_indent(u):
    return json.dumps(u, indent=4)


def _escape_dots(u):
    return u.replace('.', '[.]')


def _format_datetime(value, frmt):
    return datetime.datetime.fromtimestamp(float(value)).strftime(frmt)


def register_jinja_filters(jinja_env):
    jinja_env.filters['unquote'] = _unquote
    jinja_env.filters['tojsonsafe'] = _to_json_safe
    jinja_env.filters['tojsonindent'] = _to_json_indent
    jinja_env.filters['escape_dots'] = _escape_dots
    jinja_env.filters['format_datetime'] = _format_datetime
