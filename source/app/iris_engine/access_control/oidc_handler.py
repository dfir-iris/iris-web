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

    # Normalize issuer URL - strip trailing slash to prevent "Unknown Issuer" errors
    issuer_url = app.config.get("OIDC_ISSUER_URL", "").rstrip('/')
    client_id = app.config.get("OIDC_CLIENT_ID")
    client_secret = app.config.get("OIDC_CLIENT_SECRET")

    # Check for explicit JWKS URI (e.g., Azure single-tenant with appid)
    jwks_uri = app.config.get("OIDC_JWKS_URI")

    try:
        if jwks_uri:
            # Manual configuration with explicit JWKS URI
            app.logger.info(f"Using explicit JWKS URI: {jwks_uri}")

            op_info = ProviderConfigurationResponse(
                issuer=issuer_url,
                authorization_endpoint=app.config.get("OIDC_AUTH_ENDPOINT"),
                token_endpoint=app.config.get("OIDC_TOKEN_ENDPOINT"),
                end_session_endpoint=app.config.get("OIDC_END_SESSION_ENDPOINT"),
                jwks_uri=jwks_uri
            )
            client.handle_provider_config(op_info, issuer_url)
        else:
            # Auto-discovery (standard OIDC flow)
            app.logger.info("Using OIDC auto-discovery")
            client.provider_config(issuer_url)

    except Exception as e:
        app.logger.error(f"OIDC configuration failed: {e}")
        raise

    # Client Registration
    info = {
        "client_id": client_id,
        "client_secret": client_secret
    }
    client_reg = RegistrationResponse(**info)
    client.store_registration_info(client_reg)

    return client