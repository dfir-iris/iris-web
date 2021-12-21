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

# IMPORTS ------------------------------------------------
from flask import Blueprint
from flask import render_template, request, url_for, redirect

from app.util import admin_required

from app import bc
from app.forms import RegisterForm
from app.models.models import User

register_blueprint = Blueprint('register',
                               __name__,
                               template_folder='templates')


# CONTENT ------------------------------------------------

@register_blueprint.route('/register', methods=['GET', 'POST'])
@admin_required
def register(caseid, url_redir):
    if url_redir:
        return redirect(url_for('register.register', cid=caseid))

    # declare the Registration Form
    form = RegisterForm(request.form)

    msg = None

    if request.method == 'GET':
        return render_template('register.html', form=form, msg=msg)

    # check if both http method is POST and form is valid on submit
    if form.validate_on_submit():

        # assign form data to variables
        username = request.form.get('username', '', type=str)
        name = request.form.get('name', '', type=str).capitalize()
        password = request.form.get('password', '', type=str)
        email = request.form.get('email', '', type=str)

        # filter User out of database through username
        user = User.query.filter_by(user=username).first()

        # filter User out of database through username
        user_by_email = User.query.filter_by(email=email).first()

        if user or user_by_email:
            msg = 'Error: User exists!'

        else:

            pw_hash = bc.generate_password_hash(password.encode('utf8')).decode('utf8')

            user = User(username, name, email, pw_hash, True)

            user.save()

            msg = 'User created, please <a href="' + url_for('login.login') + '">login</a>'

    else:
        msg = 'Input error'

    return render_template('register.html', form=form, msg=msg)
