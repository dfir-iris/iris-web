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


def get_oidc_client(config, logger) -> Client:
    client = Client(client_authn_method=CLIENT_AUTHN_METHOD)

    issuer = config.get("OIDC_ISSUER_URL")

    # Try dynamic discovery first. If the well-known endpoint is
    # reachable and well-formed, every endpoint URL (authorization,
    # token, userinfo, end-session, ...) is populated on the client.
    discovery_error = None
    try:
        client.provider_config(issuer)
    except Exception as e:
        discovery_error = e
        logger.warning(
            "OIDC discovery failed for issuer %s — falling back to "
            "environment variables. Error: %s", issuer, e,
        )

        op_info = ProviderConfigurationResponse(
            issuer=issuer,
            authorization_endpoint=config.get("OIDC_AUTH_ENDPOINT"),
            token_endpoint=config.get("OIDC_TOKEN_ENDPOINT"),
            end_session_endpoint=config.get("OIDC_END_SESSION_ENDPOINT"),
        )

        client.handle_provider_config(op_info, op_info['issuer'])

    # Fail loud at startup rather than letting the request-time code
    # blow up later inside oic with the famously opaque
    # `argument of type 'NoneType' is not iterable`. If we get here
    # with no authorization_endpoint, the operator either hit a
    # discovery error AND didn't set OIDC_AUTH_ENDPOINT, or the
    # discovery doc itself was missing the field.
    if not getattr(client, "authorization_endpoint", None):
        msg = (
            "OIDC client could not resolve authorization_endpoint. "
            "Check that the IRIS app container can reach "
            f"{issuer!r}/.well-known/openid-configuration "
            "(set OIDC_ISSUER_URL correctly + verify network + TLS), "
            "or set OIDC_AUTH_ENDPOINT / OIDC_TOKEN_ENDPOINT / "
            "OIDC_END_SESSION_ENDPOINT in iris-web/.env to bypass "
            "discovery."
        )
        if discovery_error is not None:
            msg += f" Discovery error was: {discovery_error}"
        raise RuntimeError(msg)

    info = {
        "client_id": config.get("OIDC_CLIENT_ID"),
        "client_secret": config.get("OIDC_CLIENT_SECRET")
    }
    client_reg = RegistrationResponse(**info)
    client.store_registration_info(client_reg)

    return client
