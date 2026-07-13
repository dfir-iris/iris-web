from functools import wraps
from flask import request, g
from flask_login import current_user
import jwt

from app import app
from app.business.users import users_get_active
from app.models.errors import ObjectNotFoundError
from app.blueprints.rest.endpoints import response_api_error


def _safe_get_active(user_id):
    # The identifier on a token/session may point at a user that has since
    # been deleted or deactivated. Callers translate the None into either
    # "invalid" (JWT — where the caller *did* present a signed identity
    # that we're rejecting) or a plain unauthenticated fallthrough for
    # legacy/session paths. Without this we'd propagate
    # ObjectNotFoundError up to the Flask exception handler and log a
    # 500 for what is really just a stale credential.
    try:
        return users_get_active(user_id)
    except ObjectNotFoundError:
        return None


def _jwt_user():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None

    try:
        payload = jwt.decode(
            auth.split(" ", 1)[1],
            app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        return "invalid"

    if payload.get("type") != "access":
        return "invalid"

    # Step-1 tokens (password validated but MFA not yet verified) must not
    # admit the bearer to protected endpoints. Treating them as `invalid`
    # rather than `None` short-circuits the legacy/session fallthrough — a
    # step-1 access token shouldn't quietly promote to a session login.
    if payload.get("mfa_required") and not payload.get("mfa_verified"):
        return "invalid"

    user = _safe_get_active(payload["user_id"])
    # Signed token for a user that no longer exists → reject outright,
    # don't quietly fall through to legacy/session auth.
    return user if user is not None else "invalid"


def _legacy_token_user():
    if not hasattr(g, "auth_user"):
        return None
    return _safe_get_active(g.auth_user["user_id"])


def _session_user():
    if not current_user.is_authenticated:
        return None
    return _safe_get_active(current_user.id)


def api_auth(*, require_mfa: bool = False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _jwt_user()

            if user == "invalid":
                return response_api_error("Invalid token", 401)

            if user is None:
                user = _legacy_token_user()

            if user is None:
                user = _session_user()

            if user is None:
                return response_api_error("Unauthorized", 401)

            if (
                require_mfa
                and app.config.get("MFA_ENABLED")
                and not user.mfa_setup_complete
            ):
                return response_api_error("MFA required", 403)

            g.api_user = user
            return fn(*args, **kwargs)

        return wrapper
    return decorator
