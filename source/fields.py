import enum
import warnings
from functools import partial

from promise import Promise, is_thenable
from sqlalchemy.orm.query import Query

from graphene.relay import Connection, ConnectionField
from graphene.relay.connection import connection_adapter, page_info_adapter
from graphql_relay import connection_from_array_slice

from graphene_sqlalchemy.batching import get_batch_resolver
from graphene_sqlalchemy.filters import BaseTypeFilter
from graphene_sqlalchemy.utils import (
    SQL_VERSION_HIGHER_EQUAL_THAN_1_4,
    EnumValue,
    get_nullable_type,
    get_query,
    get_session,
)

if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
    from sqlalchemy.ext.asyncio import AsyncSession


class SlicedResult:
    def __init__(self, data, start_offset, total):
        self._data = data
        self._start = start_offset
        self._total = total

    def __getitem__(self, index: slice) -> any:
        x = (index.start - self._start)
        print(x)
        y = (index.stop - self._start)
        print(y)
        return self._data[x: y]

    def __len__(self) -> int:
        return self._total


class SQLAlchemyConnectionField(ConnectionField):
    @property
    def type(self):
        from graphene_sqlalchemy.types import SQLAlchemyObjectType

        type_ = super(ConnectionField, self).type
        nullable_type = get_nullable_type(type_)
        if issubclass(nullable_type, Connection):
            return type_
        assert issubclass(nullable_type, SQLAlchemyObjectType), (
            "SQLALchemyConnectionField only accepts SQLAlchemyObjectType types, not {}"
        ).format(nullable_type.__name__)
        assert nullable_type.connection, "The type {} doesn't have a connection".format(
            nullable_type.__name__
        )
        assert type_ == nullable_type, (
            "Passing a SQLAlchemyObjectType instance is deprecated. "
            "Pass the connection type instead accessible via SQLAlchemyObjectType.connection"
        )
        return nullable_type.connection

    def __init__(self, type_, *args, **kwargs):
        print("sql init")
        nullable_type = get_nullable_type(type_)
        # Handle Sorting and Filtering
        if (
            "sort" not in kwargs
            and nullable_type
            and issubclass(nullable_type, Connection)
        ):
            # Let super class raise if type is not a Connection
            try:
                kwargs.setdefault("sort", nullable_type.Edge.node._type.sort_argument())
            except (AttributeError, TypeError):
                raise TypeError(
                    'Cannot create sort argument for {}. A model is required. Set the "sort" argument'
                    " to None to disabling the creation of the sort query argument".format(
                        nullable_type.__name__
                    )
                )
        elif "sort" in kwargs and kwargs["sort"] is None:
            del kwargs["sort"]

        if (
            "filter" not in kwargs
            and nullable_type
            and issubclass(nullable_type, Connection)
        ):
            # Only add filtering if a filter argument exists on the object type
            filter_argument = nullable_type.Edge.node._type.get_filter_argument()
            if filter_argument:
                kwargs.setdefault("filter", filter_argument)
        elif "filter" in kwargs and kwargs["filter"] is None:
            del kwargs["filter"]

        super(SQLAlchemyConnectionField, self).__init__(type_, *args, **kwargs)

    @property
    def model(self):
        return get_nullable_type(self.type)._meta.node._meta.model

    @classmethod
    def get_query(cls, model, info, sort=None, filter=None, **args):
        query = get_query(model, info.context)
        if sort is not None:
            if not isinstance(sort, list):
                sort = [sort]
            sort_args = []
            # ensure consistent handling of graphene Enums, enum values and
            # plain strings
            for item in sort:
                if isinstance(item, enum.Enum):
                    sort_args.append(item.value.value)
                elif isinstance(item, EnumValue):
                    sort_args.append(item.value)
                else:
                    sort_args.append(item)
            query = query.order_by(*sort_args)

        if filter is not None:
            assert isinstance(filter, dict)
            filter_type: BaseTypeFilter = type(filter)
            query, clauses = filter_type.execute_filters(query, filter)
            query = query.filter(*clauses)
        return query

    @classmethod
    def resolve_connection(cls, connection_type, model, info, args, resolved):
        print("resolve connection")
        session = get_session(info.context)
        if resolved is None:
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):

                async def get_result():
                    return await cls.resolve_connection_async(
                        connection_type, model, info, args, resolved
                    )

                return get_result()

            else:
                resolved = cls.get_query(model, info, **args)
        if isinstance(resolved, Query):
            _len = resolved.count()
        else:
            _len = len(resolved)

        def adjusted_connection_adapter(edges, pageInfo):
            return connection_adapter(connection_type, edges, pageInfo)

        connection = connection_from_array_slice(
            array_slice=resolved,
            args=args,
            slice_start=0,
            array_length=_len,
            array_slice_length=_len,
            connection_type=adjusted_connection_adapter,
            edge_type=connection_type.Edge,
            page_info_type=page_info_adapter,
        )
        connection.iterable = resolved
        connection.length = _len
        return connection

    @classmethod
    async def resolve_connection_async(
        cls, connection_type, model, info, args, resolved
    ):
        session = get_session(info.context)
        if resolved is None:
            query = cls.get_query(model, info, **args)
            resolved = (await session.scalars(query)).all()
            print(resolved)
        if isinstance(resolved, Query):
            _len = resolved.count()
        else:
            _len = len(resolved)

        def adjusted_connection_adapter(edges, pageInfo):
            return connection_adapter(connection_type, edges, pageInfo)

        connection = connection_from_array_slice(
            array_slice=resolved,
            args=args,
            slice_start=0,
            array_length=_len,
            array_slice_length=_len,
            connection_type=adjusted_connection_adapter,
            edge_type=connection_type.Edge,
            page_info_type=page_info_adapter,
        )
        print(connection)
        connection.iterable = resolved
        connection.length = _len
        return connection

    @classmethod
    def connection_resolver(cls, resolver, connection_type, model, root, info, **args):
        resolved = resolver(root, info, **args)

        on_resolve = partial(cls.resolve_connection, connection_type, model, info, args)
        if is_thenable(resolved):
            return Promise.resolve(resolved).then(on_resolve)

        return on_resolve(resolved)

    def wrap_resolve(self, parent_resolver):
        return partial(
            self.connection_resolver,
            parent_resolver,
            get_nullable_type(self.type),
            self.model,
        )


# TODO Remove in next major version
class UnsortedSQLAlchemyConnectionField(SQLAlchemyConnectionField):
    def __init__(self, type_, *args, **kwargs):
        if "sort" in kwargs and kwargs["sort"] is not None:
            warnings.warn(
                "UnsortedSQLAlchemyConnectionField does not support sorting. "
                "All sorting arguments will be ignored."
            )
            kwargs["sort"] = None
        warnings.warn(
            "UnsortedSQLAlchemyConnectionField is deprecated and will be removed in the next "
            "major version. Use SQLAlchemyConnectionField instead and either don't "
            "provide the `sort` argument or set it to None if you do not want sorting.",
            DeprecationWarning,
        )
        super(UnsortedSQLAlchemyConnectionField, self).__init__(type_, *args, **kwargs)


class BatchSQLAlchemyConnectionField(SQLAlchemyConnectionField):
    """
    This is currently experimental.
    The API and behavior may change in future versions.
    Use at your own risk.
    """

    @classmethod
    def connection_resolver(cls, resolver, connection_type, model, root, info, **args):
        if root is None:
            resolved = resolver(root, info, **args)
            on_resolve = partial(
                cls.resolve_connection, connection_type, model, info, args
            )
        else:
            relationship_prop = None
            for relationship in root.__class__.__mapper__.relationships:
                if relationship.mapper.class_ == model:
                    relationship_prop = relationship
                    break
            resolved = get_batch_resolver(relationship_prop)(root, info, **args)
            on_resolve = partial(
                cls.resolve_connection, connection_type, root, info, args
            )

        if is_thenable(resolved):
            return Promise.resolve(resolved).then(on_resolve)

        return on_resolve(resolved)

    @classmethod
    def from_relationship(cls, relationship, registry, **field_kwargs):
        model = relationship.mapper.entity
        model_type = registry.get_type_for_model(model)
        return cls(
            model_type.connection,
            resolver=get_batch_resolver(relationship),
            **field_kwargs,
        )


def default_connection_field_factory(relationship, registry, **field_kwargs):
    model = relationship.mapper.entity
    model_type = registry.get_type_for_model(model)
    return __connectionFactory(model_type, **field_kwargs)


# TODO Remove in next major version
__connectionFactory = UnsortedSQLAlchemyConnectionField


def createConnectionField(type_, **field_kwargs):
    warnings.warn(
        "createConnectionField is deprecated and will be removed in the next "
        "major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.",
        DeprecationWarning,
    )
    return __connectionFactory(type_, **field_kwargs)


def registerConnectionFieldFactory(factoryMethod):
    warnings.warn(
        "registerConnectionFieldFactory is deprecated and will be removed in the next "
        "major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.",
        DeprecationWarning,
    )
    global __connectionFactory
    __connectionFactory = factoryMethod


def unregisterConnectionFieldFactory():
    warnings.warn(
        "registerConnectionFieldFactory is deprecated and will be removed in the next "
        "major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.",
        DeprecationWarning,
    )
    global __connectionFactory
    __connectionFactory = UnsortedSQLAlchemyConnectionField
