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

from app.datamgmt.case.case_rfiles_db import add_rfile
from app.models import CaseReceivedFile


class EvidenceStorage(object):
    @staticmethod
    def is_evidence_registered(case_id, sha256):
        data = CaseReceivedFile.query.filter(
            CaseReceivedFile.case_id == case_id,
            CaseReceivedFile.file_hash == sha256
        ).first()
        return True if data else False

    @staticmethod
    def add_evidence(case_id, filename, description, size, sha256, date_added, user_id):
        evidence = CaseReceivedFile()

        evidence.file_description = description
        evidence.filename = filename
        evidence.file_size = size
        evidence.file_hash = sha256

        return add_rfile(evidence, case_id, user_id)
