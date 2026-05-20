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

from app.logger import logger


class BusinessProcessingError(Exception):

    def __init__(self, message, data=None):
        self._message = message
        self._data = data

    def get_message(self):
        return self._message

    def get_data(self):
        return self._data


class ObjectNotFoundError(BusinessProcessingError):

    def __init__(self):
        super().__init__('Object not found')


class UnhandledBusinessError(BusinessProcessingError):

    def __init__(self, message, data=None):
        super().__init__(message, data)
        logger.exception(message)
        logger.exception(data)


class ElementInUseError(BusinessProcessingError):

    pass
