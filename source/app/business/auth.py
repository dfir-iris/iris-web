from app import bc, app
from app.datamgmt.manage.manage_users_db import get_active_user_by_login
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema

log = app.logger

def _retrieve_user_by_username(username:str):
    """
    Retrieve the user object by username.

    :param username: Username
    :return: User object if found, None
    """
    user = get_active_user_by_login(username)
    if not user:
        track_activity(f'someone tried to log in with user \'{username}\', which does not exist',
                       ctx_less=True, display_in_ui=False)
    return user

def validate_ldap_login(username: str, password:str, local_fallback: bool = True):
    """
    Validate the user login using LDAP authentication.

    :param username: Username
    :param password: Password
    :param local_fallback: If True, will fallback to local authentication if LDAP fails.
    :return: User object if successful, None otherwise
    """
    try:
        if ldap_authenticate(username, password) is False:
            if local_fallback is True:
                track_activity(f'wrong login password for user \'{username}\' using LDAP auth - falling back to local based on settings',
                               ctx_less=True, display_in_ui=False)
                return validate_local_login(username, password)
            track_activity(f'wrong login password for user \'{username}\' using LDAP auth', ctx_less=True, display_in_ui=False)
            return None

        user = _retrieve_user_by_username(username)
        if not user:
            return None

        return UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)
    except Exception as e:
        log.error(e.__str__())
        return None


def validate_local_login(username: str, password: str):
    """
    Validate the user login using local authentication.

    :param username: Username
    :param password: Password

    :return: User object if successful, None otherwise
    """
    user = _retrieve_user_by_username(username)
    if not user:
        return None

    if bc.check_password_hash(user.password, password):
        return UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)

    track_activity(f'wrong login password for user \'{username}\' using local auth', ctx_less=True, display_in_ui=False)
    return None
