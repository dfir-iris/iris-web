"""v2 avatar endpoints.

Three call sites:

* `GET /api/v2/users/<id>/avatar` — any authenticated user can fetch
  any other user's avatar. The bytes are shown in mention chips, case
  contributor lists, comment bubbles, alert assignment chips, side-bar
  user menu, etc., so locking this behind `server_administrator`
  would break the feature for every non-admin viewer. The response
  carries an ETag and `Cache-Control: private, must-revalidate` so
  clients revalidate cheaply rather than re-downloading on every
  page render.

* `POST /api/v2/me/avatar` / `DELETE /api/v2/me/avatar` — self-service.
  Anyone authenticated can swap or remove their own avatar. The POST
  expects a `multipart/form-data` with an `avatar` file part; the
  handler hands the bytes to Pillow which validates the format, centre-
  crops to a square, resizes to 256x256, and re-encodes as PNG before
  hitting the DB. Polyglot uploads (HTML/SVG/JS with a JPEG header)
  get rejected at the Pillow open step.

* `POST/DELETE /api/v2/manage/users/<id>/avatar` — admin-only equivalents
  so an administrator can correct or reset a user's avatar.

Upload limits:
* 4 MB hard cap on the raw bytes (`MAX_AVATAR_BYTES`).
* Output is bounded by Pillow at 256x256 PNG (~30-80 KB).
"""
from __future__ import annotations

import io
from datetime import datetime
from datetime import timezone

from flask import Blueprint
from flask import Response
from flask import current_app
from flask import make_response
from flask import request
from PIL import Image
from PIL import UnidentifiedImageError

from sqlalchemy import func
from sqlalchemy import or_

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.users import users_get
from app.db import db
from app.models.authorization import Permissions
from app.models.authorization import User
from app.models.errors import ObjectNotFoundError


MAX_AVATAR_BYTES = 4 * 1024 * 1024  # raw upload cap before resize
TARGET_SIZE = 256                   # final output dimensions
TARGET_MIME = 'image/png'


def _normalise_image(raw: bytes) -> bytes:
    """Validate, centre-crop, resize and re-encode an upload.

    Returns the PNG bytes ready to land in the DB, or raises
    `ValueError` with a user-facing reason.
    """
    try:
        # `Image.open` is lazy; calling `.load()` forces Pillow to
        # parse the body which is what actually rejects malformed
        # / polyglot uploads. `.convert('RGBA')` normalises every
        # accepted input (jpg / png / webp / gif first frame) onto a
        # single colour model so the resize step is deterministic.
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            img = img.convert('RGBA')

            # Centre-crop to a square. Most upload helpers already
            # constrain the user to a square, but file pickers don't,
            # and a non-square upload re-encoded straight to 256x256
            # would distort the face.
            width, height = img.size
            short = min(width, height)
            left = (width - short) // 2
            top = (height - short) // 2
            img = img.crop((left, top, left + short, top + short))

            img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format='PNG', optimize=True)
            return buf.getvalue()
    except UnidentifiedImageError as exc:
        raise ValueError('File is not a recognised image') from exc
    except OSError as exc:
        # Pillow raises OSError on truncated bodies, EXIF parse
        # failures, etc. Map them all to a generic "bad image" so the
        # client gets a single error path rather than internal
        # specifics.
        raise ValueError('Could not decode image') from exc


def _serve_avatar(user) -> Response:
    """Return a 200 with the avatar bytes, or 404 when none is set."""
    blob = getattr(user, 'avatar_blob', None)
    if not blob:
        return response_api_not_found()

    mime = getattr(user, 'avatar_mime', None) or TARGET_MIME
    updated = getattr(user, 'avatar_updated_at', None)

    response = make_response(blob)
    response.headers['Content-Type'] = mime
    response.headers['Content-Length'] = str(len(blob))
    # `private` because the URL is the same for every user even
    # though the body differs by session — we don't want shared CDN
    # caches mixing bodies between viewers if one ever sits in front
    # of the SPA.
    response.headers['Cache-Control'] = 'private, max-age=60, must-revalidate'
    if updated:
        # ETag based on the millisecond timestamp gives clients a
        # cheap conditional GET path and invalidates the moment the
        # user reuploads.
        response.headers['ETag'] = f'"{int(updated.timestamp() * 1000)}"'
        response.headers['Last-Modified'] = updated.strftime('%a, %d %b %Y %H:%M:%S GMT')
    return response


def _handle_upload(user) -> Response:
    """Read the uploaded part, validate and store it on `user`."""
    file = request.files.get('avatar')
    if file is None or file.filename == '':
        return response_api_error('Missing avatar file part')

    # `content_length` is set by Flask when the multipart parser
    # discovers a Content-Length header. We also check the body
    # length explicitly below so a chunked upload can't sneak past.
    if file.content_length and file.content_length > MAX_AVATAR_BYTES:
        return response_api_error(f'Avatar exceeds {MAX_AVATAR_BYTES // (1024 * 1024)} MB')

    raw = file.read(MAX_AVATAR_BYTES + 1)
    if len(raw) > MAX_AVATAR_BYTES:
        return response_api_error(f'Avatar exceeds {MAX_AVATAR_BYTES // (1024 * 1024)} MB')

    try:
        png_bytes = _normalise_image(raw)
    except ValueError as exc:
        return response_api_error(str(exc))

    user.avatar_blob = png_bytes
    user.avatar_mime = TARGET_MIME
    user.avatar_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    return response_api_success({
        'user_id': user.id,
        'avatar_updated_at': user.avatar_updated_at.isoformat(),
        'mime': TARGET_MIME,
    })


def _clear_avatar(user) -> Response:
    user.avatar_blob = None
    user.avatar_mime = None
    user.avatar_updated_at = None
    db.session.commit()
    return response_api_deleted()


# ----- Public read endpoint --------------------------------------------------
# Lives on its own blueprint mounted at `/users` so it can carry a
# weaker permission requirement than the manage `/users` blueprint
# (which is `server_administrator`-only). Any authenticated user can
# fetch any other user's avatar.

users_public_blueprint = Blueprint('users_public_rest_v2', __name__, url_prefix='/users')


@users_public_blueprint.get('/<int:identifier>/avatar')
@ac_api_requires()
def get_user_avatar(identifier: int) -> Response:
    try:
        user = users_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    if user is None:
        return response_api_not_found()
    return _serve_avatar(user)


# Lightweight directory for the @-mention autocomplete. Any authenticated
# user can list active users so mention chips work without needing the
# admin-only /manage/users endpoint. The payload is intentionally minimal
# (id, login, name) — no email, no roles, no permissions — so it can't
# be repurposed as a permission-info leak. Bounded by `_MENTION_LIMIT`
# because the mention popup only shows a handful of results.
_MENTION_LIMIT = 50


@users_public_blueprint.get('/mentionable')
@ac_api_requires()
def get_mentionable_users() -> Response:
    """Return active users matching `?q=<prefix>` for the mention popup.

    Match is case-insensitive prefix against `user.user` (login) OR
    `user.name` (display name), plus an `ilike` fallback so mid-word
    matches also surface (e.g. `q=alice` finds "Alice Doe" and
    "malice@bar" alike). Empty `q` returns the first N active users
    which the client can then fuzzy-filter locally.
    """
    q_raw = request.args.get('q', default='', type=str) or ''
    q = q_raw.strip().lower()

    query = User.query.filter(User.active == True)  # noqa: E712
    if q:
        # Prefix match first (cheap on indexed columns), fall back to
        # substring match. Kept as one query so a single row-scan
        # answers both.
        like = f'%{q}%'
        query = query.filter(or_(
            func.lower(User.user).like(like),
            func.lower(User.name).like(like),
        ))

    # Deterministic order so paginated / infinite-scroll clients see a
    # stable list. `name` is the primary sort — display name is what
    # the user sees in the mention chip.
    rows = (
        query
        .order_by(func.lower(User.name).asc(), User.id.asc())
        .limit(_MENTION_LIMIT)
        .all()
    )

    return response_api_success({
        'data': [
            {
                'user_id': u.id,
                'user_login': u.user,
                'user_name': u.name,
            }
            for u in rows
        ],
    })


# ----- Self-service endpoints ------------------------------------------------

me_avatar_blueprint = Blueprint('me_avatar_rest_v2', __name__, url_prefix='/me')


@me_avatar_blueprint.post('/avatar')
@ac_api_requires()
def post_my_avatar() -> Response:
    user = users_get(iris_current_user.id)
    if user is None:
        return response_api_not_found()
    return _handle_upload(user)


@me_avatar_blueprint.delete('/avatar')
@ac_api_requires()
def delete_my_avatar() -> Response:
    user = users_get(iris_current_user.id)
    if user is None:
        return response_api_not_found()
    return _clear_avatar(user)


# ----- Admin endpoints -------------------------------------------------------

admin_avatar_blueprint = Blueprint(
    'admin_avatar_rest_v2', __name__, url_prefix='/manage/users'
)


@admin_avatar_blueprint.post('/<int:identifier>/avatar')
@ac_api_requires(Permissions.server_administrator)
def post_user_avatar(identifier: int) -> Response:
    try:
        user = users_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    if user is None:
        return response_api_not_found()
    return _handle_upload(user)


@admin_avatar_blueprint.delete('/<int:identifier>/avatar')
@ac_api_requires(Permissions.server_administrator)
def delete_user_avatar(identifier: int) -> Response:
    try:
        user = users_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    if user is None:
        return response_api_not_found()
    return _clear_avatar(user)


# Silence the linter — kept around in case we need to log upload
# stats or limit by admin role later.
_ = current_app
