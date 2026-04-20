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
import base64

import io
import time

import pyotp
import qrcode
from urllib.parse import urlsplit
import random
import string

# MFA hardening constants. Values are deliberately conservative — a legitimate
# user mistypes their token occasionally; an attacker brute-forcing 10^6 TOTP
# codes should not be able to linearly grind them.
_MFA_MAX_ATTEMPTS = 5
_MFA_LOCKOUT_SECONDS = 15 * 60

from oic import rndstr
from oic.oic.message import AuthorizationResponse

# IMPORTS ------------------------------------------------

from flask import Blueprint, flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user, login_required
from flask_login import login_user

from app import app
from app import bc
from app import db
from app import oidc_client
from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict

from app.forms import LoginForm, MFASetupForm
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.util import is_authentication_ldap, response_error
from app.util import is_authentication_oidc
from app.datamgmt.manage.manage_users_db import get_active_user_by_login, get_user
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
    auth_type = app.config.get('AUTHENTICATION_TYPE')

    return render_template('login.html', form=form, msg=msg, organisation_name=organisation_name,
                           login_banner=login_banner, ptfm_contact=ptfm_contact, auth_type=auth_type)


def _validate_local_login(username, password):
    user = _retrieve_user_by_username(username)
    if not user:
        return None

    if bc.check_password_hash(user.password, password):
        return user

    track_activity("wrong login password for user '{}' using local auth".format(username), ctx_less=True, display_in_ui=False)
    return None


def _validate_ldap_login(username, password, local_fallback=True):
    try:
        if ldap_authenticate(username, password) is False:
            if local_fallback is True:
                track_activity("wrong login password for user '{}' using LDAP auth - falling back to local based on settings".format(username),
                               ctx_less=True, display_in_ui=False)
                return _validate_local_login(username, password)
            track_activity("wrong login password for user '{}' using LDAP auth".format(username), ctx_less=True, display_in_ui=False)
            return None

        user = _retrieve_user_by_username(username)
        if not user:
            return None

        return user
    except Exception as e:
        log.error(e.__str__())
        return None


def _authenticate_ldap(form, username, password, local_fallback=True):
    try:
        user = _validate_ldap_login(username, password, local_fallback)
        if user is None:
            return _render_template_login(form, 'Wrong credentials. Please try again.')

        return wrap_login_user(user)

    except Exception as e:
        log.error(e.__str__())
        return _render_template_login(form, 'LDAP authentication unavailable. Check server logs')


def _authenticate_password(form, username, password):
    user = _retrieve_user_by_username(username)
    if not user or user.is_service_account:
        return _render_template_login(form, 'Wrong credentials. Please try again.')

    if bc.check_password_hash(user.password, password):
        return wrap_login_user(user)

    track_activity("wrong login password for user '{}' using local auth".format(username), ctx_less=True,
                   display_in_ui=False)
    return _render_template_login(form, 'Wrong credentials. Please try again.')


# CONTENT ------------------------------------------------
# Authenticate user
if app.config.get("AUTHENTICATION_TYPE") in ["local", "ldap", "oidc"]:
    @login_blueprint.route('/login', methods=['GET', 'POST'])
    def login():
        #session.permanent = True

        if current_user.is_authenticated:
            return redirect(url_for('index.index'))

        if is_authentication_oidc() and app.config.get('AUTHENTICATION_LOCAL_FALLBACK') is False:
            return redirect(url_for('login.oidc_login'))

        form = LoginForm(request.form)

        # check if both http method is POST and form is valid on submit
        if not form.is_submitted() and not form.validate():

            return _render_template_login(form, None)

        # assign form data to variables
        username = request.form.get('username', '', type=str)
        password = request.form.get('password', '', type=str)

        if is_authentication_ldap() is True:
            return _authenticate_ldap(form, username, password, app.config.get('AUTHENTICATION_LOCAL_FALLBACK'))

        return _authenticate_password(form, username, password)

if is_authentication_oidc():
    @login_blueprint.route('/oidc-login')
    def oidc_login():
        if current_user.is_authenticated:
            return redirect(url_for('index.index'))

        session["oidc_state"] = rndstr()
        session["oidc_nonce"] = rndstr()

        args = {
            "client_id": oidc_client.client_id,
            "response_type": "code",
            "scope": app.config.get("OIDC_SCOPES"),
            "nonce": session["oidc_nonce"],
            "redirect_uri": url_for("login.oidc_authorise", _external=True),
            "state": session["oidc_state"]
        }

        auth_req = oidc_client.construct_AuthorizationRequest(request_args=args)
        login_url = auth_req.request(oidc_client.authorization_endpoint)

        return redirect(login_url)

if is_authentication_oidc():
    @login_blueprint.route('/oidc-authorize')
    def oidc_authorise():
        auth_resp = oidc_client.parse_response(AuthorizationResponse, info=request.args,
                                    sformat="dict")

        if auth_resp["state"] != session["oidc_state"]:
            track_activity(
                f"OIDC session state '{auth_resp['state']}' does not match authorization state '{session['oidc_state']}'",
                ctx_less=True,
                display_in_ui=False,
            )
            return redirect(url_for("login.login"))

        args = {
            "code": auth_resp["code"],
        }

        access_token_resp = oidc_client.do_access_token_request(state=auth_resp["state"], request_args=args)

        # not all providers set email by default, use preferred_username where it's missing
        # Use the mapping from the configuration or default to email or preferred_username if not set
        email_field = app.config.get("OIDC_MAPPING_EMAIL")
        username_field = app.config.get("OIDC_MAPPING_USERNAME")

        user_login = access_token_resp['id_token'].get(username_field) or access_token_resp['id_token'].get(email_field)
        user_name = access_token_resp['id_token'].get(email_field) or access_token_resp['id_token'].get(username_field)

        user = get_user(user_login, 'user')

        if not user:
            log.warning(f"OIDC user {user_login} not found in database")
            if app.config.get("AUTHENTICATION_CREATE_USER_IF_NOT_EXIST") is False:
                log.warning(f"Authentication is set to not create user if not exists")
                track_activity(
                    f"OIDC user {user_login} not found in database",
                    ctx_less=True,
                    display_in_ui=False,
                )
                return response_error("User not found in IRIS", 404)

            log.info(f"Creating OIDC user {user_login} in database")
            track_activity(
                f"Creating OIDC user {user_login} in database",
                ctx_less=True,
                display_in_ui=False,
            )

            # generate random password
            password = ''.join(random.choices(string.printable[:-6], k=16))

            user = create_user(
                        user_name=user_name,
                        user_login=user_login,
                        user_email=user_login,
                        user_password=bc.generate_password_hash(password.encode('utf8')).decode('utf8'),
                        user_active=True,
                        user_is_service_account=False
                )

        if user and not user.active:
            return response_error("User not active in IRIS", 403)

        return wrap_login_user(user, is_oidc=True)

def wrap_login_user(user, is_oidc=False):

    session['username'] = user.user

    if 'SERVER_SETTINGS' not in app.config:
        app.config['SERVER_SETTINGS'] = get_server_settings_as_dict()

    if app.config['SERVER_SETTINGS']['enforce_mfa'] is True and is_oidc is False:
        # MFA state must be bound to the specific user who verified — a flat
        # boolean would let a prior verified session admit a different user on
        # the same browser (e.g. shared device, attacker knows user B's
        # password and reuses user A's mfa_verified=True).
        verified_for = session.get('mfa_verified_for_user_id')
        if verified_for != user.id:
            # If the session is currently MFA-locked out, don't reset state
            # here — an attacker who re-POSTs /login mustn't be able to zero
            # out the fail counter and get a fresh burst of 5 tokens.
            locked_until = session.get('mfa_lockout_until')
            if locked_until and locked_until > time.time():
                flash('Too many attempts. Please try again later.', 'danger')
                return redirect(url_for('login.login'))

            # Mark this browser session as the one that just passed password
            # auth for this user. mfa_setup / mfa_verify will refuse to run
            # for any other user id, preventing cross-user MFA handler abuse.
            session['pre_mfa_user_id'] = user.id
            session['mfa_fail_count'] = 0
            session.pop('mfa_lockout_until', None)
            session.pop('pending_mfa_secret', None)
            return redirect(url_for('mfa_verify'))

    login_user(user)

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

    track_activity("user '{}' successfully logged-in".format(user.user), ctx_less=True, display_in_ui=False)

    next_url = None
    if request.args.get('next'):
        next_url = request.args.get('next') if 'cid=' in request.args.get('next') else request.args.get('next') + '?cid=' + str(user.ctx_case)

    if not next_url or urlsplit(next_url).netloc != '':
        next_url = url_for('index.index', cid=user.ctx_case)

    return redirect(next_url)


def _get_pre_mfa_user():
    """Return the user this session just passed password auth for, or None.

    The pre_mfa_user_id marker is set exclusively by wrap_login_user after a
    successful password (or LDAP) check. Any MFA handler that runs without it
    is being hit directly by an attacker and must be refused.
    """
    pre_mfa_user_id = session.get('pre_mfa_user_id')
    if pre_mfa_user_id is None:
        return None
    return get_user(pre_mfa_user_id, id_key='id')


def _clear_pre_mfa_state(preserve_lockout=False):
    """Clear the markers that prove this session just passed password auth.

    preserve_lockout: when True, keep the lockout timestamp and fail counter
    so that an attacker cannot wipe a brute-force lockout simply by hitting
    /login again.
    """
    session.pop('pre_mfa_user_id', None)
    session.pop('pending_mfa_secret', None)
    if not preserve_lockout:
        session.pop('mfa_fail_count', None)
        session.pop('mfa_lockout_until', None)


def _mfa_is_locked_out():
    locked_until = session.get('mfa_lockout_until')
    if locked_until and locked_until > time.time():
        return True
    if locked_until and locked_until <= time.time():
        # Lockout expired — reset the counter so the user gets a fresh window.
        session.pop('mfa_lockout_until', None)
        session['mfa_fail_count'] = 0
    return False


def _register_mfa_failure(user, reason):
    session['mfa_fail_count'] = session.get('mfa_fail_count', 0) + 1
    track_activity(
        f'Failed MFA {reason} for user {user.user} (attempt {session["mfa_fail_count"]}/{_MFA_MAX_ATTEMPTS})',
        ctx_less=True, display_in_ui=False
    )
    if session['mfa_fail_count'] >= _MFA_MAX_ATTEMPTS:
        session['mfa_lockout_until'] = time.time() + _MFA_LOCKOUT_SECONDS
        # Drop the pending-MFA marker so the attacker has to go back through
        # password auth before they get another burst of attempts. Preserve
        # the lockout timestamp so a fresh /login cannot wipe it.
        _clear_pre_mfa_state(preserve_lockout=True)
        session.pop('username', None)


@app.route('/auth/mfa-setup', methods=['GET', 'POST'])
def mfa_setup():
    user = _get_pre_mfa_user()
    if user is None:
        return redirect(url_for('login.login'))

    # mfa_setup is only for users who haven't completed MFA yet (fresh
    # accounts, or admin-reset accounts where mfa_setup_complete was cleared).
    # A user who already has MFA enrolled must go through mfa_verify — this
    # prevents the "I know the password, let me overwrite the enrolled secret
    # with one I control" bypass.
    if user.mfa_setup_complete and user.mfa_secrets:
        return redirect(url_for('mfa_verify'))

    if _mfa_is_locked_out():
        flash('Too many attempts. Please try again later.', 'danger')
        return redirect(url_for('login.login'))

    form = MFASetupForm()

    if form.submit() and form.validate():

        token = form.token.data
        user_password = form.user_password.data
        # The secret MUST come from the server-side session, never from the
        # submitted form. Trusting form.mfa_secret let an attacker enrol a
        # secret of their choosing and immediately log in.
        mfa_secret = session.get('pending_mfa_secret')
        if not mfa_secret:
            flash('MFA setup expired. Please restart the login flow.', 'danger')
            return redirect(url_for('login.login'))

        totp = pyotp.TOTP(mfa_secret)

        if totp.verify(token):
            has_valid_password = False
            if is_authentication_ldap() is True:
                if _validate_ldap_login(user.user, user_password,
                                        local_fallback=app.config.get('AUTHENTICATION_LOCAL_FALLBACK')):
                    has_valid_password = True

            elif bc.check_password_hash(user.password, user_password):
                has_valid_password = True

            if not has_valid_password:
                _register_mfa_failure(user, 'setup (invalid password)')
                flash('Invalid password. Please try again.', 'danger')
                return render_template('mfa_setup.html', form=form)

            user.mfa_secrets = mfa_secret
            user.mfa_setup_complete = True
            db.session.commit()
            track_activity(f'MFA setup successful for user {user.user}', ctx_less=True, display_in_ui=False)

            # Setup succeeded — promote this session to MFA-verified for this
            # user and clear the pre-MFA markers. Without this, wrap_login_user
            # would loop straight back to mfa_verify.
            session['mfa_verified_for_user_id'] = user.id
            _clear_pre_mfa_state()
            return wrap_login_user(user)
        else:
            _register_mfa_failure(user, 'setup (invalid token)')
            flash('Invalid token or password. Please try again.', 'danger')

    # Generate a fresh secret on every GET and stash it in the session. The
    # client only sees the QR code and the base32 key for manual entry; it
    # never sends the secret back.
    temp_otp_secret = pyotp.random_base32()
    session['pending_mfa_secret'] = temp_otp_secret
    otp_uri = pyotp.TOTP(temp_otp_secret).provisioning_uri(user.email, issuer_name="IRIS")
    img = qrcode.make(otp_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_str = base64.b64encode(buf.getvalue()).decode()

    return render_template('mfa_setup.html', form=form, img_data=img_str, otp_setup_key=temp_otp_secret)


@app.route('/auth/mfa-verify', methods=['GET', 'POST'])
def mfa_verify():
    user = _get_pre_mfa_user()
    if user is None:
        return redirect(url_for('login.login'))

    # Redirect user to MFA setup if MFA is not fully set up
    if not user.mfa_secrets or not user.mfa_setup_complete:
        track_activity(f'MFA setup required for user {user.user}', ctx_less=True, display_in_ui=False)
        return redirect(url_for('mfa_setup'))

    if _mfa_is_locked_out():
        flash('Too many attempts. Please try again later.', 'danger')
        return redirect(url_for('login.login'))

    form = MFASetupForm()
    form.user_password.data = 'not required for verification'

    if form.submit() and form.validate():
        token = form.token.data
        if not token:
            flash('Token is required.', 'danger')
            return render_template('mfa_verify.html', form=form)

        totp = pyotp.TOTP(user.mfa_secrets)
        if totp.verify(token):
            track_activity(f'MFA verification successful for user {user.user}', ctx_less=True, display_in_ui=False)
            # Bind the MFA-verified marker to this specific user id so that a
            # later login attempt for a different user on the same browser
            # session cannot reuse it.
            session['mfa_verified_for_user_id'] = user.id
            _clear_pre_mfa_state()
            return wrap_login_user(user)
        else:
            _register_mfa_failure(user, 'verification (invalid token)')
            flash('Invalid token. Please try again.', 'danger')

    return render_template('mfa_verify.html', form=form)