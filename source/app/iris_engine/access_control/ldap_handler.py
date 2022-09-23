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
import ldap3.core.exceptions
import ssl
from ldap3 import Connection
from ldap3 import Server
from ldap3 import Tls
from ldap3.utils import conv

from app import app

log = app.logger


def ldap_authenticate(ldap_user_name, ldap_user_pwd):
    """
    Authenticate to the LDAP server
    """
    ldap_user_name = conv.escape_filter_chars(ldap_user_name)
    ldap_user = f"{app.config.get('LDAP_USER_PREFIX')}{ldap_user_name.strip()},{app.config.get('LDAP_USER_SUFFIX')}"

    tls_configuration = Tls(validate=ssl.CERT_REQUIRED,
                            version=app.config.get('LDAP_TLS_VERSION'))

    server = Server(f'{app.config.get("LDAP_CONNECT_STRING")}',
                    use_ssl=app.config.get('LDAP_USE_SSL'),
                    tls=tls_configuration)

    conn = Connection(server,
                      user=ldap_user,
                      password=ldap_user_pwd,
                      auto_referrals=False,
                      authentication="SIMPLE")

    try:

        if not conn.bind():
            log.error(f"Cannot bind to ldap server: {conn.last_error} ")
            return False

    except ldap3.core.exceptions.LDAPInvalidCredentialsResult as e:
        log.error(f'Wrong credentials. Error : {e.__str__()}')
        return False

    except Exception as e:
        raise Exception(e.__str__())

    log.info(f"Successful authenticated user")

    return True
