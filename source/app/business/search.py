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

from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.comments import search_comments
from app.datamgmt.case.case_notes_db import search_notes
from app.datamgmt.case.case_iocs_db import search_iocs
from app.datamgmt.case.case_db import search_case_summary

def search(search_type, search_value):
    track_activity(f'started a global search for {search_value} on {search_type}')

    files = []
    if search_type == 'case_summary':
        files = search_case_summary(search_value)

    if search_type == 'ioc':
        files = search_iocs(search_value)

    if search_type == 'notes' and search_value:
        files = search_notes(search_value)

    if search_type == 'comments':
        files = search_comments(search_value)
    return files
