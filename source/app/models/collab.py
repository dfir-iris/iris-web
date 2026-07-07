#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Persistent state for the real-time collaborative editor.

One row per document (case note, case summary, war-room note, sitrep).
The row holds the Yjs update blob so late joiners and warm restarts
can hydrate without going back to the source column. The `content_md`
copy is a convenience — cold reads that don't want to boot a Y.Doc
can consume it directly, and the periodic flush pipes it back to the
authoritative source column (`notes.note_content`, `cases.description`,
`war_room_note.content`, `war_room_sitrep.body_md`).

`doc_name` is a stable string of the form `<kind>:<id>`:
  * `note:<note_id>`
  * `case-summary:<case_id>`
  * `war-room-note:<war_room_note_id>`
  * `sitrep:<sitrep_id>`

Kept as a text key (rather than modelling four FKs) because the
collab layer treats every editable document the same shape, and
scoping by kind is cheaper than a polymorphic join.
"""

from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import LargeBinary
from sqlalchemy import Text

from app.db import db


class CollabDoc(db.Model):
    __tablename__ = 'collab_doc'

    doc_name = Column(Text, primary_key=True)
    y_state = Column(LargeBinary, nullable=True)
    content_md = Column(Text, nullable=True)
    last_flushed_at = Column(DateTime, nullable=True)
    updated_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    # No ORM `updated_by` relationship intentionally: nothing in the
    # collab codepath reads it, and adding a string-name `relationship('User')`
    # risks the exact class of mapper-config-time resolution error that
    # broke UserActivity.war_room earlier in this branch. The FK is
    # enough for the audit column.
