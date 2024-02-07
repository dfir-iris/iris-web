#  IRIS Source Code
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

# IMPORTS ------------------------------------------------

from flask import Blueprint
from flask import render_template

from app import app
from app.iris_engine.demo_builder import gen_demo_admins
from app.iris_engine.demo_builder import gen_demo_users

demo_blueprint = Blueprint(
    'demo-landing',
    __name__,
    template_folder='templates'
)

log = app.logger

if app.config.get('DEMO_MODE_ENABLED') == 'True':
    @demo_blueprint.route('/welcome', methods=['GET'])
    def demo_landing():
        iris_version = app.config.get('IRIS_VERSION')
        demo_domain = app.config.get('DEMO_DOMAIN')
        seed_user = app.config.get('DEMO_USERS_SEED')
        seed_adm = app.config.get('DEMO_ADM_SEED')
        adm_count = int(app.config.get('DEMO_ADM_COUNT', 4))
        users_count = int(app.config.get('DEMO_USERS_COUNT', 10))

        demo_users = [
            {'username': username, 'password': pwd, 'role': 'Admin'} for _, username, pwd, _ in gen_demo_admins(adm_count, seed_adm)
        ]
        demo_users += [
            {'username': username, 'password': pwd, 'role': 'User'} for _, username, pwd, _ in gen_demo_users(users_count, seed_user)
        ]

        return render_template(
            'demo-landing.html',
            iris_version=iris_version,
            demo_domain=demo_domain,
            demo_users=demo_users
        )
