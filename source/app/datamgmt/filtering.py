#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
import json

from sqlalchemy import JSON, String, Text, inspect, or_, not_, and_
from sqlalchemy.dialects.postgresql import JSONB

from app import app
from app.models.errors import BusinessProcessingError
from app.datamgmt.conversions import convert_sort_direction
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.authorization import RESTRICTED_USER_FIELDS

log = app.logger


def apply_filters(query, model, filter_params: dict):
    """
    Apply filters to the query based on the given filter parameters.
    For string fields (e.g., Text, String) a case-insensitive partial match is used,
    while for other field types an exact match is applied.
    """
    # Create a mapping of column names to column objects.
    mapper = inspect(model)
    columns_dict = {column.key: column for column in mapper.columns}

    for field, value in filter_params.items():
        if field in columns_dict:
            column = columns_dict[field]
            model_field = getattr(model, field)
            # Use ilike for string types for partial, case-insensitive matching.
            if isinstance(column.type, String) or isinstance(column.type, Text):
                query = query.filter(model_field.ilike(f"%{value}%"))
            else:
                query = query.filter(model_field == value)
    return query


def build_condition(column, operator, value):
    """
    Build a SQLAlchemy condition based on a column, an operator, and a value.
    Supports relationship attributes if needed.
    """
    if hasattr(column, 'property') and hasattr(column.property, 'local_columns'):
        # It's a relationship attribute
        fk_cols = list(column.property.local_columns)
        if operator in ['in', 'not_in']:
            if len(fk_cols) == 1:
                fk_col = fk_cols[0]
                if operator == 'in':
                    return fk_col.in_(value)
                return ~fk_col.in_(value)
            raise NotImplementedError(
                "in_() on a relationship with multiple FK columns not supported. Specify a direct column."
            )
        raise ValueError(
            "Non-in operators on relationships require specifying a related model column, e.g., owner.id or assets.asset_name."
        )
    if operator == 'not' or operator == 'neq':
        return column != value
    if operator == 'in':
        return column.in_(value)
    if operator == 'not_in':
        return ~column.in_(value)
    if operator == 'eq':
        return column == value
    if operator == 'like':
        return column.ilike(f"%{value}%")
    if operator == 'not_like':
        return ~column.ilike(f"%{value}%")
    raise ValueError(f"Unsupported operator: {operator}")


def combine_conditions(conditions, logical_operator):
    """
    Combine a list of conditions using the provided logical operator.
    Supported operators: 'and' (default), 'or', 'not'
    """
    if len(conditions) > 1:
        if logical_operator == 'or':
            return or_(*conditions)
        if logical_operator == 'not':
            return not_(and_(*conditions))
        # Default to 'and'
        return and_(*conditions)
    if conditions:
        return conditions[0]
    return None


def apply_custom_conditions(query, model, custom_conditions, relationship_model_map=None):
    """
    Apply custom conditions to the query.

    Each item in `custom_conditions` is either:
      * A **leaf** — dict with `field` / `operator` / `value`.
      * A **group** — dict with `logic` ('and'/'or'/'not') and its own
        `conditions` list, recursively. Nested groups let callers build
        arbitrary AND/OR trees (e.g. `(A and B) or (C and D)`) — the
        rule / flow condition builders on the frontend rely on this.

    Existing callers that pass a flat list of leaves continue to work
    unchanged; the recursion only kicks in when an item omits `field`.

    An optional `relationship_model_map` maps relationship names to
    models, used for dot-notation fields like `assets.asset_name`.
    """
    conditions = []
    if relationship_model_map is None:
        relationship_model_map = {}

    joined_relationships = set()

    for cond in custom_conditions:
        if not isinstance(cond, dict):
            raise ValueError(f'condition entry must be a dict, got {type(cond).__name__}')

        # Group form: recurse and combine.
        if 'field' not in cond and 'conditions' in cond:
            inner_logic = cond.get('logic', 'and')
            inner_items = cond.get('conditions') or []
            query, inner_leaves = apply_custom_conditions(
                query, model, inner_items, relationship_model_map
            )
            combined = combine_conditions(inner_leaves, inner_logic)
            if combined is not None:
                conditions.append(combined)
            continue

        # Leaf form.
        field_path = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')
        if '.' in field_path:
            head, tail = field_path.split('.', 1)
            # A dotted path can mean two things:
            #   (a) a relationship path like `assets.asset_name` — join
            #       the related model and treat the tail as a column
            #       name on that model
            #   (b) a JSON(B) column path like `alert_context.foo.bar` —
            #       the head is a JSON column on this model and the
            #       tail(s) drill into the document
            # We prefer (b) when the head *is* a column on this model
            # AND its type is JSON/JSONB. Otherwise we fall back to (a).
            head_attr = getattr(model, head, None)
            head_is_json_column = (
                head_attr is not None
                and hasattr(head_attr, 'type')
                and isinstance(head_attr.type, (JSON, JSONB))
            )

            if head_is_json_column:
                condition = build_json_condition(head_attr, tail, operator, value)
                conditions.append(condition)
                continue

            if head not in relationship_model_map:
                raise ValueError(f"Unknown relationship or JSON column: {head}")
            related_model = relationship_model_map[head]
            if head not in joined_relationships:
                query = query.join(getattr(model, head))
                joined_relationships.add(head)

            related_field = get_field_from_model(related_model, tail)

            condition = build_condition(related_field, operator, value)
            conditions.append(condition)
        else:
            field = get_field_from_model(model, field_path)

            condition = build_condition(field, operator, value)
            conditions.append(condition)

    return query, conditions


def build_json_condition(json_column, path, operator, value):
    """Build a SQLAlchemy condition against a nested JSON(B) path.

    `path` is a dot-separated string like `foo.bar.baz`; each segment
    becomes a key traversal step (Postgres `->` for intermediate
    JSON-returning steps and `->>` (`astext`) for the final compare so
    the RHS is a text scalar that composes with `ilike`/`in`/`==`).

    Array indices work implicitly — Postgres accepts numeric-looking
    strings as array indices via `->`. We keep the dotted spelling
    (`items.0.value`) rather than invent a bracket syntax, so rule
    authors don't have to know two spellings.

    Numeric comparisons (`gte`/`lte`) cast the extracted text to
    numeric first; unsupported operators bubble up from build_condition
    via a shared path.
    """
    segments = path.split('.')
    if not segments:
        raise ValueError("JSON path must not be empty")

    expr = json_column
    for segment in segments[:-1]:
        expr = expr[segment]
    # Final step: extract as text so the comparison RHS is a string
    # and existing operator handling (`ilike`, `in_`, `==`) applies
    # without further coercion. Postgres' `->>` operator returns text.
    final = expr[segments[-1]].astext

    if operator in ('gte', 'lte'):
        # Cast to numeric on the fly so `alert_context.count >= 10`
        # compares as a number. Text-wise `'2' > '10'` would be true
        # otherwise (lexicographic).
        from sqlalchemy import cast, Numeric
        casted = cast(final, Numeric)
        return casted >= value if operator == 'gte' else casted <= value
    if operator in ('not', 'neq'):
        return final != value
    if operator == 'in':
        return final.in_(value)
    if operator == 'not_in':
        return ~final.in_(value)
    if operator == 'eq':
        return final == value
    if operator == 'like':
        return final.ilike(f"%{value}%")
    if operator == 'not_like':
        return ~final.ilike(f"%{value}%")
    raise ValueError(f"Unsupported operator for JSON path: {operator}")


def get_field_from_model(model, field_path):
    """
    Return the field from the given model.
    """
    field = getattr(model, field_path, None)
    if field is None:
        raise ValueError(f"Field '{field_path}' not found in {model.__name__}")

    if field in RESTRICTED_USER_FIELDS:
        raise ValueError(f"Field '{field_path}' not found in {model.__name__}")

    return field


def get_filtered_data(model,
                      base_filter,
                      pagination_parameters: PaginationParameters,
                      request_parameters: dict,
                      relationship_model_map: dict = None):
    """
    Generic function to filter, sort, and paginate query results for a given model.

    :param model: The SQLAlchemy model to query.
    :param base_filter: A SQLAlchemy filter condition to apply (or None).
    :param pagination_parameters: An instance of PaginationParameters.
    :param request_parameters: Dictionary of additional filter parameters.
    :param relationship_model_map: A dictionary mapping relationship names to models.
    :return: Paginated query results.
    """
    # Create a shallow copy to avoid modifying the original dictionary
    filter_params = request_parameters.copy()

    # Remove pagination related keys.
    for key in ['page', 'per_page', 'order_by', 'direction']:
        filter_params.pop(key, None)

    # Start query and apply base filter if provided.
    query = model.query
    if base_filter is not None:
        query = query.filter(base_filter)

    # Apply generic filters.
    query = apply_filters(query, model, filter_params)

    # Process any custom conditions.
    custom_conditions_param = filter_params.get('custom_conditions')
    logical_operator = filter_params.get('logical_operator') or 'or'
    if custom_conditions_param:
        try:
            custom_conditions = json.loads(custom_conditions_param)
            if not isinstance(custom_conditions, list):
                raise BusinessProcessingError('custom_conditions should be a list of condition objects')

            query, conditions = apply_custom_conditions(query, model, custom_conditions, relationship_model_map)
            query = query.filter(combine_conditions(conditions, logical_operator))
        except Exception as e:
            log.exception(e)
            raise BusinessProcessingError(f'Error parsing custom_conditions: {e}')

    return paginate(model, pagination_parameters, query)


def paginate(model, pagination_parameters: PaginationParameters, query):
    order_by = pagination_parameters.get_order_by()
    if order_by is not None and hasattr(model, order_by):
        order_func = convert_sort_direction(pagination_parameters.get_direction())
        column = getattr(model, order_by)
        query = query.order_by(order_func(column))

    # Paginate and return the results.
    result = query.paginate(
        page=pagination_parameters.get_page(),
        per_page=pagination_parameters.get_per_page(),
        error_out=False
    )
    return result
