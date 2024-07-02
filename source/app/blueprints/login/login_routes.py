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
from urllib.parse import urlsplit

# IMPORTS ------------------------------------------------
import os
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import login_user
from flask_login import logout_user
import urllib.parse
import random

from app import app
from app import bc
from app import db

from app.forms import LoginForm
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.access_control.oidc_proxy_handler import oidc_proxy_authenticate, oidc_proxy_userinfo, oidc_proxy_logout
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.util import is_authentication_ldap
from app.util import is_authentication_oidc_proxy
from app.util import generate_random_pw
from app.datamgmt.manage.manage_users_db import get_active_user_by_login
from app.datamgmt.manage.manage_users_db import create_user


login_blueprint = Blueprint(
    'login',
    __name__,
    template_folder='templates'
)

log = app.logger


# filter User out of database through username
def _retrieve_user_by_username(username):
    user = get_active_user_by_login(username)
    if not user:
        track_activity("someone tried to log in with user '{}', which does not exist".format(username),
                       ctx_less=True, display_in_ui=False)
    return user


def _render_template_login(form, msg):
    organisation_name = app.config.get('ORGANISATION_NAME')
    login_banner = app.config.get('LOGIN_BANNER_TEXT')
    ptfm_contact = app.config.get('LOGIN_PTFM_CONTACT')

    return render_template('login.html', form=form, msg=msg, organisation_name=organisation_name,
                           login_banner=login_banner, ptfm_contact=ptfm_contact, logo=app.config.get("IRIS_LOGO"))

def _authenticate_ldap(form, username, password, local_fallback=True):
    try:
        if ldap_authenticate(username, password) is False:
            if local_fallback is True:
                track_activity("wrong login password for user '{}' using LDAP auth - falling back to local based on settings".format(username),
                                 ctx_less=True, display_in_ui=False)
                
                return _authenticate_password(form, username, password)
            
            track_activity("wrong login password for user '{}' using LDAP auth".format(username),
                           ctx_less=True, display_in_ui=False)
            return _render_template_login(form, 'Wrong credentials. Please try again.')

        user = _retrieve_user_by_username(username)
        if not user:
            return _render_template_login(form, 'Wrong credentials. Please try again.')
        else:
            app.config.update({"AUTHENTICATION_TYPE_TMP":"ldap"})
            session["AUTHENTICATION_TYPE"] = "ldap"


        return wrap_login_user(user)
    except Exception as e:
        log.error(e.__str__())
        return _render_template_login(form, 'LDAP authentication unavailable. Check server logs')

def _authenticate_oidc_proxy(form, username, password, local_fallback=True):
    try:
        issuer_url = app.config.get('OIDC_ISSUER_URL')
        client_id = app.config.get('AUTHENTICATION_CLIENT_ID')
        client_secret = app.config.get('AUTHENTICATION_CLIENT_SECRET')
        redirect_uri = urllib.parse.quote_plus(f"https://{app.config.get('IRIS_UPSTREAM_SERVER')}/auth")
        track_activity("redirect to auth uri",
                ctx_less=True, display_in_ui=False)
        return redirect(f"{issuer_url}/protocol/openid-connect/auth?client_id={client_id}&client_secret={client_secret}&response_type=code&redirect_uri={redirect_uri}&scope=openid%20profile%20email%20address%20phone&nonce=None")

    except Exception as e:
        log.error(e.__str__())
        return _render_template_login(form, 'OIDC authentication unavailable. Check server logs')

def _authenticate_password(form, username, password):
    user = _retrieve_user_by_username(username)
    if not user or user.is_service_account:
        return _render_template_login(form, 'Wrong credentials. Please try again.')

    if bc.check_password_hash(user.password, password):
        app.config.update({"AUTHENTICATION_TYPE_TMP":"local"})
        session["AUTHENTICATION_TYPE"] = "local"
        return wrap_login_user(user)

    track_activity("wrong login password for user '{}' using local auth".format(username), ctx_less=True,
                   display_in_ui=False)
    return _render_template_login(form, 'Wrong credentials. Please try again.')


# CONTENT ------------------------------------------------
# Authenticate user
if app.config.get("AUTHENTICATION_TYPE") in ["local", "ldap", "oidc_proxy"]:
    @login_blueprint.route('/login', methods=['GET', 'POST'])
    def login():
        session.permanent = True
        if current_user.is_authenticated:
            track_activity("user is authenticated",
                    ctx_less=True, display_in_ui=False)
            return redirect(url_for('index.index'))
        else:
            track_activity("not authenticated",
                    ctx_less=True, display_in_ui=False)

        form = LoginForm(request.form)

        # check if both http method is POST and form is valid on submit
        session_state = request.args.get('session_state')
        if not form.is_submitted() and not form.validate() and session_state==None:
            track_activity("form not submitted and not validated",
                    ctx_less=True, display_in_ui=False)
            return _render_template_login(form, None)
        else:
            track_activity("form submitted or validated",
                    ctx_less=True, display_in_ui=False)

        # assign form data to variables
        username = request.form.get('username', '', type=str)
        password = request.form.get('password', '', type=str)
        sso = request.form.get('sso', '', type=str) 

        if is_authentication_ldap() is True:
            return _authenticate_ldap(form, username, password, app.config.get('AUTHENTICATION_LOCAL_FALLBACK'))
        elif is_authentication_oidc_proxy() is True and sso=="sso":
            track_activity("sso flow",
                    ctx_less=True, display_in_ui=False)
            return _authenticate_oidc_proxy(form, username, password)
        else:
            track_activity("password fallback local",
                    ctx_less=True, display_in_ui=False)
            return _authenticate_password(form, username, password)


    @login_blueprint.route('/auth', methods=['GET', 'POST'])
    def auth():
        form = LoginForm(request.form)
        track_activity("getting OIDC token",
                ctx_less=True, display_in_ui=False)
        session_state = request.args.get('session_state')
        code = request.args.get('code')
        if code!=None: 
            success = oidc_proxy_authenticate(code)
            if success:
                userinfo = oidc_proxy_userinfo(session["oidc_access_token"])
                track_activity(f"userinfo: {str(userinfo)}",
                        ctx_less=True, display_in_ui=False)
                if "email" in userinfo.keys():
                    username = userinfo["email"]
                    session["oidc_username"]=username
                    user = _retrieve_user_by_username(username)
                    if not user:
                        track_activity("first login, creating OIDC user in database",
                                ctx_less=True, display_in_ui=False)
                        password = generate_random_pw(random.randint(15,25)) # This password won't be used to login, because oidc_proxy is activated
                        user = create_user(user_name=username,
                                    user_login=username,
                                    user_email=username,
                                    user_password=password, 
                                    user_active=True,
                                    user_is_service_account=False)
                    else:
                        track_activity("user already created in database",
                                ctx_less=True, display_in_ui=False)
                else:
                    track_activity("email not defined in LDAP, please contact your administrator",
                            ctx_less=True, display_in_ui=False)
                    logout_user()
                    oidc_proxy_logout()
                    return _render_template_login(form, 'email not defined in LDAP, please contact your administrator')
                return wrap_login_user(user)
        else:
            return _render_template_login(form)

def wrap_login_user(user):
    login_user(user)

    track_activity("user '{}' successfully logged-in".format(user.user), ctx_less=True, display_in_ui=False)
    caseid = user.ctx_case
    session['permissions'] = ac_get_effective_permissions_of_user(user)

    if caseid is None:
        case = Cases.query.order_by(Cases.case_id).first()
        user.ctx_case = case.case_id
        user.ctx_human_case = case.name
        db.session.commit()

    session['current_case'] = {
        'case_name': user.ctx_human_case,
        'case_info': "",
        'case_id': user.ctx_case
    }

    track_activity("user '{}' successfully logged-in".format(user), ctx_less=True, display_in_ui=False)

    next_url = None
    if request.args.get('next'):
        next_url = request.args.get('next') if 'cid=' in request.args.get('next') else request.args.get('next') + '?cid=' + str(user.ctx_case)

    if not next_url or urlsplit(next_url).netloc != '':
        next_url = url_for('index.index', cid=user.ctx_case)
    
    track_activity(f"wrap_login_user - next_url:{next_url}",
            ctx_less=True, display_in_ui=False)
    
    return redirect(next_url)
