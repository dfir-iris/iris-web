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

from sqlalchemy import String, Text, inspect, or_, not_, and_

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
    if operator == 'not':
        return column != value
    if operator == 'in':
        return column.in_(value)
    if operator == 'not_in':
        return ~column.in_(value)
    if operator == 'eq':
        return column == value
    if operator == 'like':
        return column.ilike(f"%{value}%")
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

    return query, conditions


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
