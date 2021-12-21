#!/usr/bin/env python3
#
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

import os

from app import app


def build_upload_path(case_customer, case_name, module, create=False):
    """
    Create a path for the upload of the files, according to the specifications of the case
    :param case_customer: Customer name linked to the case
    :param case_name:  Name of the case
    :param module: Name of the module which will handle the data
    :param create: True if the path needs to be created, else false
    :return: The built full path, None if errors
    """
    try:
        if case_name and case_customer and module:
            path = "{customer}/{case}/{module}/".format(
                customer=case_customer.strip().replace('.', '').replace(' ', '').replace('/', ''),
                case=case_name.strip().replace('.', '').replace(' ', '_').replace('/', '').lower(),
                module=module.replace('.', '').replace(' ', '_').replace('/', '')
            )

            fpath = os.path.join(app.config['UPLOADED_PATH'], path)

            if create:
                os.makedirs(os.path.join(app.config['UPLOADED_PATH'], path), exist_ok=True)

            return fpath

        return None

    except Exception as e:
        print(e)
        return None