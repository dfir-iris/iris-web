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
import pyotp
import qrcode
import random
import string
import json
from flask import Blueprint, flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from oic import rndstr
from oic.oic.message import AuthorizationResponse

from app import app
from app import bc
from app.db import db
from app import oidc_client
from app.blueprints.access_controls import is_authentication_oidc
from app.blueprints.access_controls import is_authentication_ldap
from app.blueprints.responses import response_error
from app.business.auth import validate_ldap_login
from app.business.users import retrieve_user_by_username
from app.business.auth import wrap_login_user
from app.datamgmt.manage.manage_users_db import create_user
from app.datamgmt.manage.manage_users_db import update_user_groups
from app.datamgmt.manage.manage_users_db import get_user
from app.forms import LoginForm, MFASetupForm
from app.blueprints.iris_user import iris_current_user
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.business.auth import generate_auth_tokens
from app.schema.marshables import UserSchema

login_blueprint = Blueprint("login", __name__, template_folder="templates")

log = app.logger


# filter User out of database through username


def _render_template_login(form, msg):
    organisation_name = app.config.get("ORGANISATION_NAME")
    login_banner = app.config.get("LOGIN_BANNER_TEXT")
    ptfm_contact = app.config.get("LOGIN_PTFM_CONTACT")
    auth_type = app.config.get("AUTHENTICATION_TYPE")

    return render_template(
        "login.html",
        form=form,
        msg=msg,
        organisation_name=organisation_name,
        login_banner=login_banner,
        ptfm_contact=ptfm_contact,
        auth_type=auth_type,
    )


def _validate_local_login(username, password):
    user = retrieve_user_by_username(username)
    if not user:
        return None

    if bc.check_password_hash(user.password, password):
        return user

    track_activity(
        f"wrong login password for user '{username}' using local auth",
        ctx_less=True,
        display_in_ui=False,
    )
    return None


def _authenticate_ldap(form, username, password, local_fallback=True):
    try:
        user = validate_ldap_login(username, password, local_fallback)
        if user is None:
            return _render_template_login(form, "Wrong credentials. Please try again.")

        user_data = UserSchema(
            exclude=["user_password", "mfa_secrets", "webauthn_credentials"]
        ).dump(user)

        # Generate auth tokens for API access
        tokens = generate_auth_tokens(user)
        user_data.update({"tokens": tokens})

        return wrap_login_user(user_data)

    except Exception as e:
        log.error(e.__str__())
        return _render_template_login(
            form, "LDAP authentication unavailable. Check server logs"
        )


def _authenticate_password(form, username, password):
    user = retrieve_user_by_username(username)
    if not user or user.is_service_account:
        return _render_template_login(form, "Wrong credentials. Please try again.")

    if bc.check_password_hash(user.password, password):
        return wrap_login_user(user)

    track_activity(
        f"wrong login password for user '{username}' using local auth",
        ctx_less=True,
        display_in_ui=False,
    )
    return _render_template_login(form, "Wrong credentials. Please try again.")


# Authenticate user
if app.config.get("AUTHENTICATION_TYPE") in ["local", "ldap", "oidc"]:

    @login_blueprint.route("/login", methods=["GET", "POST"])
    def login():
        if iris_current_user.is_authenticated:
            return redirect(url_for("index.index"))

        if (
            is_authentication_oidc()
            and app.config.get("AUTHENTICATION_LOCAL_FALLBACK") is False
        ):
            return redirect(url_for("login.oidc_login"))

        form = LoginForm(request.form)

        # check if both http method is POST and form is valid on submit
        if not form.is_submitted() and not form.validate():
            return _render_template_login(form, None)

        # assign form data to variables
        username = request.form.get("username", "", type=str)
        password = request.form.get("password", "", type=str)

        if is_authentication_ldap() is True:
            return _authenticate_ldap(
                form,
                username,
                password,
                app.config.get("AUTHENTICATION_LOCAL_FALLBACK"),
            )

        return _authenticate_password(form, username, password)


if is_authentication_oidc():

    @login_blueprint.route("/oidc-login")
    def oidc_login():
        if iris_current_user.is_authenticated:
            return redirect(url_for("index.index"))

        session["oidc_state"] = rndstr()
        session["oidc_nonce"] = rndstr()

        xf_proto = request.headers.get("X-Forwarded-Proto")
        xf_host = request.headers.get("X-Forwarded-Host")

        if xf_proto:
            xf_proto = xf_proto.split(",")[0].strip()
        if xf_host:
            xf_host = xf_host.split(",")[0].strip()

        redirect_uri = url_for("login.oidc_authorise", _external=True)

        if xf_proto and xf_host:
            redirect_uri = f"{xf_proto}://{xf_host}/oidc-authorize"

        args = {
            "client_id": oidc_client.client_id,
            "response_type": "code",
            "scope": app.config.get("OIDC_SCOPES"),
            "nonce": session["oidc_nonce"],
            "redirect_uri": redirect_uri,
            "state": session["oidc_state"],
        }

        auth_req = oidc_client.construct_AuthorizationRequest(request_args=args)
        login_url = auth_req.request(oidc_client.authorization_endpoint)

        return redirect(login_url)


if is_authentication_oidc():

    @login_blueprint.route("/oidc-authorize")
    def oidc_authorise():
        auth_resp = oidc_client.parse_response(
            AuthorizationResponse, info=request.args, sformat="dict"
        )

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

        xf_proto = request.headers.get("X-Forwarded-Proto")
        xf_host = request.headers.get("X-Forwarded-Host")

        if xf_proto:
            xf_proto = xf_proto.split(",")[0].strip()
        if xf_host:
            xf_host = xf_host.split(",")[0].strip()

        if xf_proto and xf_host:
            public_base = f"{xf_proto}://{xf_host}"
            args["redirect_uri"] = f"{public_base}/oidc-authorize"

        access_token_resp = oidc_client.do_access_token_request(
            state=auth_resp["state"], request_args=args
        )

        # not all providers set email by default, use preferred_username where it's missing
        # Use the mapping from the configuration or default to email or preferred_username if not set
        email_field = app.config.get("OIDC_MAPPING_EMAIL")
        username_field = app.config.get("OIDC_MAPPING_USERNAME")
        usergroup_field = app.config.get("OIDC_MAPPING_USERGROUP")
        userroles_mapping_field = app.config.get("OIDC_MAPPING_ROLES")
        try:
            if "id_token" in access_token_resp and access_token_resp["id_token"]:
                claims = access_token_resp["id_token"]
            else:
                if "access_token" not in access_token_resp:
                    err = access_token_resp.get("error")
                    desc = access_token_resp.get("error_description")
                    log.error(
                        f"OIDC authentication failed: token response missing access_token (error={err}, desc={desc})"
                    )
                    track_activity(
                        f"OIDC authentication failed: token response missing access_token (error={err}, desc={desc})",
                        ctx_less=True,
                        display_in_ui=False,
                    )
                    return redirect(url_for("login.login"))

                claims = oidc_client.do_user_info_request(
                    state=auth_resp["state"],
                    access_token=access_token_resp["access_token"],
                )

            user_login = claims.get(username_field) or claims.get(email_field)
            user_name = claims.get(email_field) or claims.get(username_field)

            if usergroup_field is not None:
                user_group = claims.get(usergroup_field)
            else:
                user_group = None

            if not user_login:
                log.error(
                    "OIDC authentication failed: username or email not found in id_token"
                )
                track_activity(
                    "OIDC authentication failed: username or email not found in id_token",
                    ctx_less=True,
                    display_in_ui=False,
                )
                return redirect(url_for("login.login"))
        except Exception as e:
            log.error(f"OIDC authentication failed: {str(e)}")
            track_activity(
                f"OIDC authentication failed: {str(e)}",
                ctx_less=True,
                display_in_ui=False,
            )
            return redirect(url_for("login.login"))

        user = get_user(user_login, "user")

        if not user:
            log.warning(f"OIDC user {user_login} not found in database")
            if app.config.get("AUTHENTICATION_CREATE_USER_IF_NOT_EXIST") is False:
                log.warning("Authentication is set to not create user if not exists")
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
            password = "".join(random.choices(string.printable[:-6], k=16))

            user = create_user(
                user_name,
                user_login,
                bc.generate_password_hash(password.encode("utf8")).decode("utf8"),
                user_login,
                True,
                user_is_service_account=False,
            )

        if user and not user.active:
            return response_error("User not active in IRIS", 403)

        if user and (not user_group) and userroles_mapping_field:
            return response_error(
                "Required user group information missing in OIDC response", 403
            )

        if user_group:
            if not userroles_mapping_field:
                groups_list = get_groups_list()
                group_name_to_id = {
                    group.group_name: group.group_id for group in groups_list
                }
            else:
                group_name_to_id = json.loads(userroles_mapping_field)
            new_user_group = [
                group_name_to_id[group_name]
                for group_name in user_group
                if group_name in group_name_to_id
            ]
            update_user_groups(user.id, new_user_group)

        return wrap_login_user(user, is_oidc=True)


@app.route("/auth/mfa-setup", methods=["GET", "POST"])
def mfa_setup():
    user = retrieve_user_by_username(username=session["username"])
    form = MFASetupForm()

    if form.submit() and form.validate():
        token = form.token.data
        mfa_secret = form.mfa_secret.data
        user_password = form.user_password.data
        totp = pyotp.TOTP(mfa_secret)

        if totp.verify(token):
            has_valid_password = False
            if is_authentication_ldap() is True:
                if validate_ldap_login(
                    user.user,
                    user_password,
                    local_fallback=app.config.get("AUTHENTICATION_LOCAL_FALLBACK"),
                ):
                    has_valid_password = True

            elif bc.check_password_hash(user.password, user_password):
                has_valid_password = True

            if not has_valid_password:
                track_activity(
                    f"Failed MFA setup for user {user.user}. Invalid password.",
                    ctx_less=True,
                    display_in_ui=False,
                )
                flash("Invalid password. Please try again.", "danger")
                return render_template("mfa_setup.html", form=form)

            user.mfa_secrets = mfa_secret
            user.mfa_setup_complete = True
            db.session.commit()
            session["mfa_verified"] = False
            track_activity(
                f"MFA setup successful for user {user.user}",
                ctx_less=True,
                display_in_ui=False,
            )
            return wrap_login_user(user)
        track_activity(
            f"Failed MFA setup for user {user.user}. Invalid token.",
            ctx_less=True,
            display_in_ui=False,
        )
        flash("Invalid token or password. Please try again.", "danger")

    temp_otp_secret = pyotp.random_base32()
    otp_uri = pyotp.TOTP(temp_otp_secret).provisioning_uri(
        user.email, issuer_name="IRIS"
    )
    form.mfa_secret.data = temp_otp_secret
    img = qrcode.make(otp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_str = base64.b64encode(buf.getvalue()).decode()

    return render_template(
        "mfa_setup.html", form=form, img_data=img_str, otp_setup_key=temp_otp_secret
    )


@app.route("/auth/mfa-verify", methods=["GET", "POST"])
def mfa_verify():
    if "username" not in session:
        return redirect(url_for("login.login"))

    user = retrieve_user_by_username(username=session["username"])

    # Redirect user to MFA setup if MFA is not fully set up
    if not user.mfa_secrets or not user.mfa_setup_complete:
        track_activity(
            f"MFA setup required for user {user.user}",
            ctx_less=True,
            display_in_ui=False,
        )
        return redirect(url_for("mfa_setup"))

    form = MFASetupForm()
    form.user_password.data = "not required for verification"

    if form.submit() and form.validate():
        token = form.token.data
        if not token:
            flash("Token is required.", "danger")
            return render_template("mfa_verify.html", form=form)

        totp = pyotp.TOTP(user.mfa_secrets)
        if totp.verify(token):
            session.pop("username", None)
            session["mfa_verified"] = True
            track_activity(
                f"MFA verification successful for user {user.user}",
                ctx_less=True,
                display_in_ui=False,
            )
            return wrap_login_user(user)
        track_activity(
            f"Failed MFA verification for user {user.user}. Invalid token.",
            ctx_less=True,
            display_in_ui=False,
        )
        flash("Invalid token. Please try again.", "danger")

    return render_template("mfa_verify.html", form=form)
