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

# OIDC Configuration
from oic.oic import Client
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.oic.message import RegistrationResponse
from oic.oic.message import ProviderConfigurationResponse


def get_oidc_client(app) -> Client:
    client = Client(client_authn_method=CLIENT_AUTHN_METHOD)

    # retrieve provider configuration dynamically from metadata
    # or fall back to env vars
    try:
        client.provider_config(app.config.get("OIDC_ISSUER_URL"))
    except Exception as e:
        app.logger.warning(f"Could not read OIDC metadata, using environment variables - error {e}")
        op_info = ProviderConfigurationResponse(
            issuer=app.config.get("OIDC_ISSUER_URL"),
            authorization_endpoint=app.config.get("OIDC_AUTH_ENDPOINT"),
            token_endpoint=app.config.get("OIDC_TOKEN_ENDPOINT"),
            end_session_endpoint=app.config.get("OIDC_END_SESSION_ENDPOINT"),
        )

        client.handle_provider_config(op_info, op_info['issuer'])

    info = {
        "client_id": app.config.get("OIDC_CLIENT_ID"),
        "client_secret": app.config.get("OIDC_CLIENT_SECRET")
    }
    client_reg = RegistrationResponse(**info)
    client.store_registration_info(client_reg)

    return client