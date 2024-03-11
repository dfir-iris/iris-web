#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

from unittest import TestCase
from unittest import skip
from iris import Iris


class TestsWhichRequireACleanSlate(TestCase):
    """
    In this test suite, each test is started from a clean slate: the state of IRIS after a fresh install.
    This is achieved by stopping and removing containers, networks and modules (docker compose down) after each test.
    In consequence tests run in this context will be costlier.
    So, whenever possible try to avoid adding tests to this suite.
    """

    def setUp(self) -> None:
        self._subject = Iris()
        self._subject.start()

    def tearDown(self) -> None:
        self._subject.stop()

    @skip
    def test_create_case_should_add_a_new_case(self):
        """
        This test is also present in the main test suite tests.py (although in a slightly more complex form
        to be independent of the initial the database state)
        This was just to give an example of a test which requires starting from an empty database.
        It may thus be removed when we have more interesting tests to add to this suite.
        """
        self._subject.create_case()
        response = self._subject.get_cases()
        case_count = len(response['data'])
        self.assertEqual(2, case_count)
