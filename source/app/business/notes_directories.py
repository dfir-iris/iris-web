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

from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.models import NoteDirectory
from app.models.errors import ObjectNotFoundError
from app.datamgmt.case.case_notes_db import get_directory
from app.datamgmt.case.case_notes_db import delete_directory
from app.datamgmt.case.case_notes_db import paginate_notes_directories
from app.models.pagination_parameters import PaginationParameters


def notes_directories_filter(case_identifier: int, pagination_parameters: PaginationParameters):
    return paginate_notes_directories(case_identifier, pagination_parameters)


def notes_directories_create(directory: NoteDirectory):
    db.session.add(directory)
    db.session.commit()

    track_activity(f'added directory "{directory.name}"', caseid=directory.case_id)


def notes_directories_get(identifier) -> NoteDirectory:
    directory = get_directory(identifier)
    if not directory:
        raise ObjectNotFoundError()
    return directory


def notes_directories_update(directory: NoteDirectory):
    db.session.commit()

    track_activity(f'modified directory "{directory.name}"', caseid=directory.case_id)


def notes_directories_delete(directory: NoteDirectory):
    delete_directory(directory)
    track_activity(f'deleted directory "{directory.name}"', caseid=directory.case_id)
