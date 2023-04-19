#!/usr/bin/env python3
#
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
from app.datamgmt.manage.manage_users_db import create_user, get_active_user_by_login

log = app.logger


def _provision_user(connection, user_login, search_base):
    if get_active_user_by_login(user_login):
        return
    attribute_display_name = app.config.get('LDAP_USER_ATTRIBUTE_DISPLAY_NAME')
    attribute_mail = app.config.get('LDAP_USER_ATTRIBUTE_MAIL')
    attributes = []
    if attribute_display_name:
        attributes.append(attribute_display_name)
    if attribute_mail:
        attributes.append(attribute_mail)
    connection.search(search_base, '(objectClass=*)', attributes=attributes)
    entry = connection.entries[0]
    if attribute_display_name:
        user_name = entry[attribute_display_name].value
    else:
        user_name = user_login
    if attribute_mail:
        user_email = entry[attribute_mail].value
    else:
        user_email = f'{user_login}@ldap'

    log.info(f'Provisioning user "{user_login}" which is present in LDAP but not yet in database.')
    # TODO the user password is chosen randomly
    #      ideally it should be possible to create a user without providing any password
    # TODO to create the user password, we use the same code as the one to generate the administrator password in post_init.py
    #      => should factor and reuse this code bit as a function
    #      => also, it should probably be more secure to use the secrets module (instead of random)
    password = ''.join(random.choices(string.printable[:-6], k=16))
    # TODO It seems email unicity is required (a fixed email causes a problem at the second account creation)
    #      The email either comes from the ldap or is forged from the login to ensure unicity
    create_user(user_name, user_login, password, user_email, True)


def ldap_authenticate(ldap_user_name, ldap_user_pwd):
    """
    Authenticate to the LDAP server
    """
    ldap_user_pwd = conv.escape_filter_chars(ldap_user_pwd)
    if app.config.get("LDAP_AUTHENTICATION_TYPE").lower() != 'ntlm':
        ldap_user_name = conv.escape_filter_chars(ldap_user_name)
        ldap_user = f"{app.config.get('LDAP_USER_PREFIX')}{ldap_user_name.strip()},{app.config.get('LDAP_USER_SUFFIX')}"
    else:
        ldap_user = f"{ldap_user_name.strip()}"

    tls_configuration = Tls(validate=ssl.CERT_REQUIRED,
                            version=app.config.get('LDAP_TLS_VERSION'),
                            local_certificate_file=app.config.get('LDAP_SERVER_CERTIFICATE'),
                            local_private_key_file=app.config.get('LDAP_PRIVATE_KEY'),
                            local_private_key_password=app.config.get('LDAP_PRIVATE_KEY_PASSWORD'))

    server = Server(f'{app.config.get("LDAP_CONNECT_STRING")}',
                    use_ssl=app.config.get('LDAP_USE_SSL'),
                    tls=tls_configuration)

    conn = Connection(server,
                      user=ldap_user,
                      password=ldap_user_pwd,
                      auto_referrals=False,
                      authentication=app.config.get('LDAP_AUTHENTICATION_TYPE'))

    try:

        if not conn.bind():
            log.error(f"Cannot bind to ldap server: {conn.last_error} ")
            return False

        if app.config.get('LDAP_USER_PROVISIONING'):
            _provision_user(conn, ldap_user_name, ldap_user)

    except ldap3.core.exceptions.LDAPInvalidCredentialsResult as e:
        log.error(f'Wrong credentials. Error : {e.__str__()}')
        return False

    except Exception as e:
        raise Exception(e.__str__())

    log.info(f"Successful authenticated user")

    return True
