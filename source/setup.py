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

from setuptools import setup

setup(
    name='IrisWebApp',
    version='v1.4.4',
    packages=['app', 'app.models', 'app.blueprints', 'app.blueprints.case', 'app.blueprints.login',
              'app.blueprints.tasks', 'app.blueprints.manage', 'app.blueprints.search',
              'app.blueprints.context', 'app.blueprints.profile', 'app.blueprints.reports',
              'app.blueprints.register', 'app.blueprints.dashboard', 'app.iris_engine',
              'app.iris_engine.utils', 'app.iris_engine.tasker', 'app.iris_engine.piggerdb',
              'app.iris_engine.piggerdb.importer', 'app.iris_engine.reporter', 'app.iris_engine.connectors',
              'app.iris_engine.case_handler', 'app.flask_dropzone'],
    url='https://github.com/airbus-cyber/iris',
    license='LGPL v3',
    author='Airbus CyberSecurity',
    author_email='ir@cyberactionlab.net',
    description='Incident Response Investigation System - Web App'
)
