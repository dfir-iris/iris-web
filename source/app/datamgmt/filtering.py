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
from sqlalchemy import String, Text, inspect, or_, not_, and_

RESTRICTED_USER_FIELDS = {
    'password',
    'mfa_secrets',
    'webauthn_credentials',
    'api_key',
    'external_id',
    'ctx_case',
    'ctx_human_case',
    'is_service_account'
}


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
                else:
                    return ~fk_col.in_(value)
            else:
                raise NotImplementedError(
                    "in_() on a relationship with multiple FK columns not supported. Specify a direct column."
                )
        else:
            raise ValueError(
                "Non-in operators on relationships require specifying a related model column, e.g., owner.id or assets.asset_name."
            )
    if operator == 'not':
        return column != value
    elif operator == 'in':
        return column.in_(value)
    elif operator == 'not_in':
        return ~column.in_(value)
    elif operator == 'eq':
        return column == value
    elif operator == 'like':
        return column.ilike(f"%{value}%")
    else:
        raise ValueError(f"Unsupported operator: {operator}")


def combine_conditions(conditions, logical_operator):
    """
    Combine a list of conditions using the provided logical operator.
    Supported operators: 'and' (default), 'or', 'not'
    """
    if len(conditions) > 1:
        if logical_operator == 'or':
            return or_(*conditions)
        elif logical_operator == 'not':
            return not_(and_(*conditions))
        else:  # Default to 'and'
            return and_(*conditions)
    elif conditions:
        return conditions[0]
    else:
        return None


def apply_custom_conditions(query, model, custom_conditions, relationship_model_map=None):
    """
    Apply custom conditions to the query.

    The custom_conditions parameter should be a list of dict objects with the following keys:
      - 'field': a field name (or a relationship.field using dot notation)
      - 'operator': the operator (e.g., 'eq', 'like', 'in', etc.)
      - 'value': the value to compare against

    An optional relationship_model_map can be provided to map relationship names to models.
    """
    conditions = []
    if relationship_model_map is None:
        relationship_model_map = {}

    joined_relationships = set()

    for cond in custom_conditions:
        field_path = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')
        if '.' in field_path:
            # Handle related fields via dot notation
            relationship_name, related_field_name = field_path.split('.', 1)
            if relationship_name not in relationship_model_map:
                raise ValueError(f"Unknown relationship: {relationship_name}")
            related_model = relationship_model_map[relationship_name]
            # Join the relationship if not already joined
            if relationship_name not in joined_relationships:
                query = query.join(getattr(model, relationship_name))
                joined_relationships.add(relationship_name)

            related_field = get_field_from_model(related_model, related_field_name)

            condition = build_condition(related_field, operator, value)
            conditions.append(condition)
        else:
            field = get_field_from_model(model, field_path)

            condition = build_condition(field, operator, value)
            conditions.append(condition)

    return conditions


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
