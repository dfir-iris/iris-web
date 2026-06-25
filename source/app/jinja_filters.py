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

import bleach
from markupsafe import Markup


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


# Allowlist for user-defined HTML custom attributes. Matches the legacy
# do_md_filter_xss() allowlist closely so behaviour is consistent across
# sinks. Explicitly excludes script / iframe / event handlers /
# javascript: URLs. Previously the modal rendered these via `| safe`,
# which is a stored-XSS sink any caller with case-write could trigger
# (SBA-ADV-20260126-03 / CWE-79).
_ATTR_HTML_ALLOWED_TAGS = [
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'span', 'strong',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
]
_ATTR_HTML_ALLOWED_ATTRS = {
    '*': ['class', 'title'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}
_ATTR_HTML_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def _sanitize_attribute_html(value):
    if value is None:
        return ''
    cleaned = bleach.clean(
        str(value),
        tags=_ATTR_HTML_ALLOWED_TAGS,
        attributes=_ATTR_HTML_ALLOWED_ATTRS,
        protocols=_ATTR_HTML_ALLOWED_PROTOCOLS,
        strip=True,
    )
    return Markup(cleaned)


def register_jinja_filters(jinja_env):
    jinja_env.filters['unquote'] = _unquote
    jinja_env.filters['tojsonsafe'] = _to_json_safe
    jinja_env.filters['tojsonindent'] = _to_json_indent
    jinja_env.filters['escape_dots'] = _escape_dots
    jinja_env.filters['format_datetime'] = _format_datetime
    jinja_env.filters['sanitize_attribute_html'] = _sanitize_attribute_html
