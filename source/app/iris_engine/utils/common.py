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
from datetime import datetime
from jinja2.sandbox import SandboxedEnvironment

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


def parse_bf_date_format(input_str):
    date_value = input_str.strip()

    if len(date_value) == 10 and '-' not in date_value and '.' not in date_value and '/' not in date_value:
        # Assume linux timestamp, from 1966 to 2286
        date = datetime.fromtimestamp(int(date_value))
        return date

    elif len(date_value) == 13 and '-' not in date_value and '.' not in date_value and '/' not in date_value:
        # Assume microsecond timestamp
        date = datetime.fromtimestamp(int(date_value) / 1000)

        return date

    else:

        # brute force formats
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%d %H:%M%z', '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S.%f%z',
                    '%Y-%m-%d %H:%M %Z', '%Y-%m-%d %H:%M:%S %Z', '%Y-%m-%d %H:%M:%S.%f %Z',
                    '%Y-%m-%d - %H:%M:%S.%f%z',

                    '%b %d %H:%M:%S', '%Y %b %d %H:%M:%S', '%b %d %H:%M:%S %Y', '%b %d %Y %H:%M:%S',
                    '%y %b %d %H:%M:%S', '%b %d %H:%M:%S %y', '%b %d %y %H:%M:%S',

                    '%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z',
                    '%Y-%m-%dT%H:%M %Z', '%Y-%m-%dT%H:%M:%S %Z', '%Y-%m-%dT%H:%M:%S.%f %Z',

                    '%Y-%d-%m', '%Y-%d-%m %H:%M', '%Y-%d-%m %H:%M:%S', '%Y-%d-%m %H:%M:%S.%f',
                    '%Y-%d-%m %H:%M%z', '%Y-%d-%m %H:%M:%S%z', '%Y-%d-%m %H:%M:%S.%f%z',
                    '%Y-%d-%m %H:%M %Z', '%Y-%d-%m %H:%M:%S %Z', '%Y-%d-%m %H:%M:%S.%f %Z',

                    '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S.%f',
                    '%d.%m.%Y %H:%M', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M:%S.%f',
                    '%d-%m-%Y %H:%M', '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S.%f',

                    '%b %d %Y %H:%M', '%b %d %Y %H:%M:%S', '%b %d %Y %H:%M:%S',

                    '%a, %d %b %Y %H:%M:%S', '%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S.%f',
                    '%a, %d %b %y %H:%M:%S', '%a, %d %b %y %H:%M:%S %Z', '%a, %d %b %y %H:%M:%S.%f',

                    '%d %b %Y %H:%M', '%d %b %Y %H:%M:%S', '%d %b %Y %H:%M:%S.%f',
                    '%d %b %y %H:%M', '%d %b %y %H:%M:%S', '%d %b %y %H:%M:%S.%f',

                    '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', "%A, %B %d, %Y", "%A %B %d, %Y", "%A %B %d %Y",
                    '%d %B %Y'):

            try:

                date = datetime.strptime(date_value, fmt)
                return date

            except ValueError:
                pass

    return None


class IrisJinjaEnv(SandboxedEnvironment):

    def is_safe_attribute(self, obj, attr, value):
        # Extend the list of blocked attributes with magic methods and other potential unsafe attributes
        unsafe_attributes = [
            'os', 'subprocess', 'eval', 'exec', 'open', 'input', '__import__',
            '__class__', '__bases__', '__mro__', '__subclasses__', '__globals__'
        ]
        # Block access to all attributes starting and ending with double underscores
        if attr in unsafe_attributes or attr.startswith('__') and attr.endswith('__'):
            return False
        return super().is_safe_attribute(obj, attr, value)

    def call(self, obj, *args, **kwargs):
        # Block calling of functions if necessary
        # For example, block if obj is a built-in function or method
        if isinstance(obj, (type,)):
            raise Exception("Calling of built-in types is not allowed.")
        return super().call(obj, *args, **kwargs)