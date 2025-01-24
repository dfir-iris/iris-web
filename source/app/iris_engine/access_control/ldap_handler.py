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

import random
import string
import ldap3.core.exceptions
import ssl
from ldap3 import Connection
from ldap3 import Server
from ldap3 import Tls
from ldap3.utils import conv

from app import app
from app.datamgmt.manage.manage_users_db import get_active_user_by_login
from app.datamgmt.manage.manage_users_db import create_user
from app.datamgmt.manage.manage_users_db import update_user_groups
from app.datamgmt.manage.manage_groups_db import get_group_by_name
from app.datamgmt.manage.manage_groups_db import create_group

_log = app.logger
_ldap_authentication_type = app.config.get('LDAP_AUTHENTICATION_TYPE')
_attribute_unique_identifier = app.config.get('LDAP_ATTRIBUTE_IDENTIFIER')
_attribute_display_name = app.config.get('LDAP_ATTRIBUTE_DISPLAY_NAME')
_attribute_mail = app.config.get('LDAP_ATTRIBUTE_MAIL')
_ldap_group_base_dn = app.config.get('LDAP_GROUP_BASE_DN')
_ldap_user_prefix = app.config.get('LDAP_USER_PREFIX')
_ldap_user_suffix = app.config.get('LDAP_USER_SUFFIX')


def _connect(server, ldap_user, ldap_user_pwd):
    connection = Connection(server,
                            user=ldap_user,
                            password=ldap_user_pwd,
                            auto_referrals=False,
                            authentication=_ldap_authentication_type)

    try:
        if not connection.bind():
            _log.error(f"Cannot bind to ldap server: {connection.last_error} ")
            return None

    except ldap3.core.exceptions.LDAPInvalidCredentialsResult as e:
        _log.error(f'Wrong credentials. Error : {e.__str__()}')
        return None

    return connection


def _connect_bind_account(server):
    ldap_bind_dn = app.config.get('LDAP_BIND_DN')
    ldap_bind_password = app.config.get('LDAP_BIND_PASSWORD')
    return _connect(server, ldap_bind_dn, ldap_bind_password)


def _connect_user(server, ldap_user_name, ldap_user_pwd):
    ldap_user = ldap_user_name.strip()
    ldap_user = f'{_ldap_user_prefix}{ldap_user}'
    # TODO idea: ldap_user_suffix could include the ',' so that we don't need to make a special case for ntlm
    if _ldap_user_suffix and _ldap_authentication_type.lower() != 'ntlm':
        ldap_user = f'{ldap_user},{_ldap_user_suffix}'
    return _connect(server, ldap_user, ldap_user_pwd)


def _search_user_in_ldap(connection, user_login):
    search_base = app.config.get('LDAP_SEARCH_DN')
    unique_identifier = conv.escape_filter_chars(user_login)
    attributes = ['memberOf']
    if _attribute_display_name:
        attributes.append(_attribute_display_name)
    if _attribute_mail:
        attributes.append(_attribute_mail)
    connection.search(search_base, f'({_attribute_unique_identifier}={unique_identifier})', attributes=attributes)
    return connection.entries[0]


def _provision_user(user_login, ldap_user_entry):
    if _attribute_display_name:
        user_name = ldap_user_entry[_attribute_display_name].value
    else:
        user_name = user_login
    if _attribute_mail:
        user_email = ldap_user_entry[_attribute_mail].value
    else:
        user_email = f'{user_login}@ldap'

    _log.info(f'Provisioning user "{user_login}" which is present in LDAP but not yet in database.')
    # TODO the user password is chosen randomly
    #      ideally it should be possible to create a user without providing any password
    # TODO to create the user password, we use the same code as the one to generate the administrator password in post_init.py
    #      => should factor and reuse this code bit as a function
    #      => also, it should probably be more secure to use the secrets module (instead of random)
    password = ''.join(random.choices(string.printable[:-6], k=16))
    # TODO It seems email uniqueness is required (a fixed email causes a problem at the second account creation)
    #      The email either comes from the ldap or is forged from the login to ensure uniqueness
    return create_user(user_name, user_login, password, user_email, True)


def _parse_cn(distinguished_name):
    relative_distinguished_names = distinguished_name.split(',')
    common_name = relative_distinguished_names[0]
    return common_name[len('cn='):]


def _update_user_groups(user, ldap_user_entry):
    ldap_group_names = ldap_user_entry['memberOf'].value
    if ldap_group_names is None:
        ldap_group_names = []
    if isinstance(ldap_group_names, str):
        ldap_group_names = [ldap_group_names]

    groups = []
    for ldap_group_name in ldap_group_names:
        if not ldap_group_name.endswith(_ldap_group_base_dn):
            continue
        group_name = _parse_cn(ldap_group_name)
        group = get_group_by_name(group_name)
        if group is None:
            _log.warning(f'Ignoring group declared in LDAP which does not exist in DFIR-IRIS: \'{group_name}\'.')
            continue
        groups.append(group.group_id)
    update_user_groups(user.id, groups)


def ldap_authenticate(ldap_user_name, ldap_user_pwd):
    """
    Authenticate to the LDAP server
    """
    if app.config.get('LDAP_CUSTOM_TLS_CONFIG') is True:
        tls_configuration = Tls(validate=ssl.CERT_REQUIRED,
                                version=app.config.get('LDAP_TLS_VERSION'),
                                local_certificate_file=app.config.get('LDAP_SERVER_CERTIFICATE'),
                                local_private_key_file=app.config.get('LDAP_PRIVATE_KEY'),
                                local_private_key_password=app.config.get('LDAP_PRIVATE_KEY_PASSWORD'),
                                ca_certs_file=app.config.get('LDAP_CA_CERTIFICATE')
                                )

        server = Server(f'{app.config.get("LDAP_CONNECT_STRING")}',
                        use_ssl=app.config.get('LDAP_USE_SSL'),
                        tls=tls_configuration)

    else:
        server = Server(f'{app.config.get("LDAP_CONNECT_STRING")}',
                        use_ssl=app.config.get('LDAP_USE_SSL'))

    if _ldap_authentication_type.lower() != 'ntlm':
        ldap_user_name = conv.escape_filter_chars(ldap_user_name)

    connection = _connect_user(server, ldap_user_name, ldap_user_pwd)
    if not connection:
        return False

    if app.config.get('AUTHENTICATION_CREATE_USER_IF_NOT_EXIST'):
        connection = _connect_bind_account(server)
        if not connection:
            return False
        ldap_user_entry = _search_user_in_ldap(connection, ldap_user_name)
        user = get_active_user_by_login(ldap_user_name)
        if not user:
            user = _provision_user(ldap_user_name, ldap_user_entry)
        _update_user_groups(user, ldap_user_entry)

    _log.info(f"Successful authenticated user")

    return True
