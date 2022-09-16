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
from ldap3 import NTLM
from ldap3.utils import conv
from app import app

from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3 import Tls
from ldap3.core.exceptions import LDAPException, LDAPBindError

log = app.logger


def ldap_authenticate(ldap_user_name, ldap_user_pwd):
    """
    Authenticate to the LDAP server
    """
    ldap_user_name = conv.escape_filter_chars(ldap_user_name)
    ldap_user = f"uid={ldap_user_name.strip()},{app.config.get('LDAP_USER_SUFFIX')}"

    tls_configuration = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLSv1_2)
    server = Server(f'ldap://{app.config.get("LDAP_SERVER")}:{app.config.get("LDAP_PORT")}',
                    use_ssl=True,
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
        log.error('Wrong credentials')
        return False

    except Exception as e:
        raise Exception(e.__str__())

    log.info(f"Successful authenticated user")

    return True
