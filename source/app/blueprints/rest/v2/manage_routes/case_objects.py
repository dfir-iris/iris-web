#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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

"""v2 endpoints for the "Case Objects" admin family.

A single page in the legacy UI bundles five taxonomy types — asset
types, IOC types, case classifications, case states and evidence
types. The CRUD surface for each is identical in shape (list / get /
create / update / delete with substring search on a single name
field) and the only per-resource variance is the model, schema and
primary-key name. So we have one shared `TaxonomyOperations` class,
instantiate it five times with a per-resource `TaxonomyConfig`, and
register each as its own Flask sub-blueprint under
`/manage/case-objects/<resource>`.

Adding a sixth taxonomy here is a one-liner: define the config, add
the blueprint to the registration list at the bottom of the file.
"""

from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Optional
from typing import Type

from flask import Blueprint
from flask import Response
from flask import request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.datamgmt.db_operations import db_create
from app.datamgmt.db_operations import db_delete
from app.datamgmt.filtering import paginate
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.assets import AssetsType
from app.models.authorization import Permissions
from app.models.cases import CaseClassification
from app.models.cases import CaseState
from app.models.errors import ElementInUseError
from app.models.errors import ObjectNotFoundError
from app.models.evidences import EvidenceTypes
from app.models.models import IocType
from app.schema.marshables import AssetTypeSchema
from app.schema.marshables import CaseClassificationSchema
from app.schema.marshables import CaseStateSchema
from app.schema.marshables import EvidenceTypeSchema
from app.schema.marshables import IocTypeSchema
from app.schema.marshables import store_icon


@dataclass(frozen=True)
class TaxonomyConfig:
    """Per-resource configuration for `TaxonomyOperations`.

    `pk_name` is the model's primary key column name (not always `id`
    — legacy schema choices means we have `asset_id`, `type_id`,
    `state_id` and `id` floating around). `search_columns` are the
    columns to ILIKE against for the search query parameter, in
    order. `protected_check` is an optional callable that lets a
    taxonomy refuse a delete for a record the engine considers
    structural (e.g. the seeded "Open" / "Closed" case states).
    `writable_fields` is the allowlist of input fields the create /
    update endpoints will forward to the schema; anything else
    (notably the primary key) is dropped before load to close the
    mass-assignment vector reported as GHSA-w78h-mx7h-qm3h /
    SBA-ADV-20260128-01 / CWE-915. The PK is excluded on purpose:
    `update()` forces it from the URL parameter, `create()` lets the
    DB assign it.
    """

    url_prefix: str
    blueprint_name: str
    model: Type[Any]
    schema_factory: Callable[[], Any]
    pk_name: str
    search_columns: Iterable[str]
    activity_label: str
    writable_fields: Iterable[str]
    protected_check: Optional[Callable[[Any], Optional[str]]] = None


class TaxonomyOperations:
    """REST surface shared by every Case Objects sub-resource.

    Methods read the URL identifier directly off the route — Flask
    passes it as keyword `identifier`. The schema is instantiated per
    request because Marshmallow stateful validators (e.g. the
    auto-injected `verify_unique` post-load hook) sometimes carry
    state between calls when reused as a module-level singleton.
    """

    def __init__(self, config: TaxonomyConfig):
        self._config = config
        self._writable = frozenset(config.writable_fields)

    def _filter_payload(self, data):
        """Drop everything not in the per-resource writable allowlist.

        Closes the mass-assignment vector reported as GHSA-w78h-mx7h-qm3h
        / SBA-ADV-20260128-01 / CWE-915. The primary key is never in the
        allowlist — `update()` forces it from the URL parameter.
        """
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in self._writable}

    def _get(self, identifier):
        row = self._config.model.query.filter(
            getattr(self._config.model, self._config.pk_name) == identifier
        ).first()
        if row is None:
            raise ObjectNotFoundError()
        return row

    def search(self):
        pagination_parameters = parse_pagination_parameters(request)
        query = self._config.model.query
        search = (request.args.get('search') or '').strip() or None
        if search:
            needle = f'%{search}%'
            clauses = []
            for column_name in self._config.search_columns:
                column = getattr(self._config.model, column_name, None)
                if column is not None:
                    clauses.append(column.ilike(needle))
            if clauses:
                from sqlalchemy import or_
                query = query.filter(or_(*clauses))
        paginated = paginate(self._config.model, pagination_parameters, query)
        return response_api_paginated(self._config.schema_factory(), paginated)

    def read(self, identifier):
        try:
            return response_api_success(self._config.schema_factory().dump(self._get(identifier)))
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self):
        schema = self._config.schema_factory()
        try:
            request_data = self._filter_payload(request.get_json())
            row = schema.load(request_data)
            db_create(row)
            track_activity(f'Added {self._config.activity_label} {self._readable(row)}', ctx_less=True)
            return response_api_created(schema.dump(row))
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def update(self, identifier):
        schema = self._config.schema_factory()
        try:
            row = self._get(identifier)
            request_data = self._filter_payload(request.get_json())
            # Schemas with `verify_unique` post-load look at the PK on
            # the loaded instance to skip the uniqueness check against
            # the row itself — force the value here so a partial update
            # that omits the PK doesn't trip the check.
            request_data[self._config.pk_name] = identifier
            schema.load(request_data, instance=row, partial=True)
            db.session.commit()
            track_activity(f'Updated {self._config.activity_label} {self._readable(row)}', ctx_less=True)
            return response_api_success(schema.dump(row))
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            row = self._get(identifier)
            if self._config.protected_check is not None:
                msg = self._config.protected_check(row)
                if msg:
                    raise ElementInUseError(msg)
            label = self._readable(row)
            try:
                db_delete(row)
            except IntegrityError:
                # FK from cases/iocs/assets back to the taxonomy — the
                # legacy UI shows the same message on these. Surface
                # 400 rather than letting the exception bubble.
                db.session.rollback()
                raise ElementInUseError(
                    f'This {self._config.activity_label} is still referenced and cannot be deleted'
                )
            track_activity(f'Deleted {self._config.activity_label} {label}', ctx_less=True)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except ElementInUseError as e:
            return response_api_error(e.get_message())

    def _readable(self, row):
        """Pick the human-readable label for activity log lines.

        Each model has a different "display name" column; rather than
        threading it through TaxonomyConfig we just try the common
        candidates. Falls back to the PK so the activity entry is
        still searchable if a taxonomy doesn't match.
        """
        for candidate in ('name', 'asset_name', 'type_name', 'state_name'):
            value = getattr(row, candidate, None)
            if value:
                return value
        return f'#{getattr(row, self._config.pk_name, "?")}'


def _build_blueprint(config: TaxonomyConfig) -> Blueprint:
    """Wire a `TaxonomyOperations` instance into a Flask blueprint.

    Keeping the route declarations local to this factory means each
    resource gets its own URL prefix (`/asset-types`, `/ioc-types`,
    …) without copying the five identical route definitions.
    """
    blueprint = Blueprint(
        config.blueprint_name,
        __name__,
        url_prefix=f'/{config.url_prefix}',
    )
    operations = TaxonomyOperations(config)

    @blueprint.get('')
    @ac_api_requires()
    def list_taxonomy() -> Response:
        return operations.search()

    @blueprint.post('')
    @ac_api_requires(Permissions.server_administrator)
    def create_taxonomy() -> Response:
        return operations.create()

    @blueprint.get('/<int:identifier>')
    @ac_api_requires()
    def read_taxonomy(identifier: int) -> Response:
        return operations.read(identifier)

    @blueprint.put('/<int:identifier>')
    @ac_api_requires(Permissions.server_administrator)
    def update_taxonomy(identifier: int) -> Response:
        return operations.update(identifier)

    @blueprint.delete('/<int:identifier>')
    @ac_api_requires(Permissions.server_administrator)
    def delete_taxonomy(identifier: int) -> Response:
        return operations.delete(identifier)

    return blueprint


def _case_state_protected(row: CaseState) -> Optional[str]:
    """Refuse deletes for the seeded "protected" case states.

    Mirrors the legacy guard in `manage_case_state.py` — the engine
    relies on Open / Closed existing for case lifecycle.
    """
    if getattr(row, 'protected', False):
        return 'This case state is protected and cannot be deleted'
    return None


_CONFIGS = [
    TaxonomyConfig(
        url_prefix='asset-types',
        blueprint_name='case_objects_asset_types_rest_v2',
        model=AssetsType,
        schema_factory=AssetTypeSchema,
        pk_name='asset_id',
        search_columns=('asset_name', 'asset_description'),
        activity_label='asset type',
        writable_fields=('asset_name', 'asset_description',
                         'asset_icon_compromised', 'asset_icon_not_compromised'),
    ),
    TaxonomyConfig(
        url_prefix='ioc-types',
        blueprint_name='case_objects_ioc_types_rest_v2',
        model=IocType,
        schema_factory=IocTypeSchema,
        pk_name='type_id',
        search_columns=('type_name', 'type_description', 'type_taxonomy'),
        activity_label='IOC type',
        writable_fields=('type_name', 'type_description', 'type_taxonomy',
                         'type_validation_regex', 'type_validation_expect'),
    ),
    TaxonomyConfig(
        url_prefix='case-classifications',
        blueprint_name='case_objects_case_classifications_rest_v2',
        model=CaseClassification,
        schema_factory=CaseClassificationSchema,
        pk_name='id',
        search_columns=('name', 'name_expanded', 'description'),
        activity_label='case classification',
        writable_fields=('name', 'name_expanded', 'description'),
    ),
    TaxonomyConfig(
        url_prefix='case-states',
        blueprint_name='case_objects_case_states_rest_v2',
        model=CaseState,
        schema_factory=CaseStateSchema,
        pk_name='state_id',
        search_columns=('state_name', 'state_description'),
        activity_label='case state',
        protected_check=_case_state_protected,
        writable_fields=('state_name', 'state_description'),
    ),
    TaxonomyConfig(
        url_prefix='evidence-types',
        blueprint_name='case_objects_evidence_types_rest_v2',
        model=EvidenceTypes,
        schema_factory=EvidenceTypeSchema,
        pk_name='id',
        search_columns=('name', 'description'),
        activity_label='evidence type',
        writable_fields=('name', 'description'),
    ),
]


case_objects_blueprint = Blueprint('case_objects_rest_v2', __name__, url_prefix='/case-objects')

for _config in _CONFIGS:
    case_objects_blueprint.register_blueprint(_build_blueprint(_config))


# Asset-type icons -------------------------------------------------------
#
# Asset types are the only Case Object taxonomy that carries images. Two
# fields (`asset_icon_compromised` / `asset_icon_not_compromised`) store
# filenames under /static/assets/img/graph/<filename>. Uploading icons
# is a separate operation from the JSON CRUD above — multipart/form-data
# doesn't fit cleanly into the shared TaxonomyOperations contract — so
# we expose dedicated upload endpoints. The frontend orchestrates the
# two-step "create asset type → upload icon" flow.

_ASSET_TYPE_ICON_FIELDS = {'compromised', 'not_compromised'}


@case_objects_blueprint.post('/asset-types/<int:identifier>/icon/<string:field>')
@ac_api_requires(Permissions.server_administrator)
def upload_asset_type_icon(identifier: int, field: str) -> Response:
    """Upload one of an asset type's two icons.

    `field` is either `compromised` or `not_compromised`. The file
    must be sent as multipart form-data under the key `file` and pass
    the existing `allowed_file_icon` check (png/svg only). On success
    the new filename is persisted on the column
    `asset_icon_<field>` and the full updated row is returned so the
    frontend can refresh its detail pane in one round-trip.
    """
    if field not in _ASSET_TYPE_ICON_FIELDS:
        return response_api_error(f"Unknown icon field: {field}")

    asset_type = AssetsType.query.filter(AssetsType.asset_id == identifier).first()
    if asset_type is None:
        return response_api_not_found()

    upload = request.files.get('file')
    if upload is None or not upload.filename:
        return response_api_error('No file uploaded')

    stored_filename, message = store_icon(upload)
    if stored_filename is None:
        return response_api_error(message or 'Icon upload failed')

    column_name = f'asset_icon_{field}'
    setattr(asset_type, column_name, stored_filename)
    db.session.commit()
    track_activity(
        f'Updated icon {field} for asset type {asset_type.asset_name}',
        ctx_less=True,
    )
    return response_api_success(AssetTypeSchema().dump(asset_type))
