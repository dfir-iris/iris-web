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

"""
Compatibility shim: re-export comment-related models from `models.py`.

This prevents duplicate declarative class registrations while keeping
imports like `from app.models.comments import Comments` working.
"""

from app.models.models import (
    Comments,
    EventComments,
    TaskComments,
    IocComments,
    AssetComments,
    EvidencesComments,
    NotesComments,
)

__all__ = [
    "Comments",
    "EventComments",
    "TaskComments",
    "IocComments",
    "AssetComments",
    "EvidencesComments",
    "NotesComments",
]
