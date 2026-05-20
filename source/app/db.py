#  IRIS Source Code
#  Copyright (C) 2025 - Airbus CyberSecurity (SAS)
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

from functools import partial
import json
import collections

from flask_sqlalchemy import SQLAlchemy


SQLALCHEMY_ENGINE_OPTIONS = {
    "json_deserializer": partial(json.loads, object_pairs_hook=collections.OrderedDict),
    "pool_pre_ping": True
}

db = SQLAlchemy(engine_options=SQLALCHEMY_ENGINE_OPTIONS)  # flask-sqlalchemy
