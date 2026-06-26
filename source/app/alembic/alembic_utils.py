from alembic import op
from sqlalchemy import inspect
from sqlalchemy import text


# All three helpers below now reuse the bind that alembic already
# opened for the current upgrade transaction (`op.get_bind()`).
#
# The previous implementation called `engine_from_config(...)` per
# call which spun up a brand new SQLAlchemy engine — and never
# disposed it. Each leaked engine kept a connection pool of 5 + 10
# overflow connections alive against Postgres. A single migration
# run that hits these helpers a handful of times can therefore
# exhaust `max_connections`, and the app start-up sequence loops
# this every time the container restarts. The end-user-visible
# symptom is `FATAL: sorry, too many clients already` shortly after
# boot.
#
# `op.get_bind()` returns the connection alembic is *already* using
# for the migration, so we ride on top of it instead of opening a
# parallel one. It's also faster — no extra TCP/SSL handshake per
# helper call.


def _table_has_column(table_name, column_name):
    """Return True when `table_name.column_name` exists in the DB."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = {c['name'] for c in inspector.get_columns(table_name)}
    return column_name in columns


def _has_table(table_name):
    """Return True when `table_name` exists in the current schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    """Return True when an index named `index_name` exists on `table_name`."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = inspector.get_indexes(table_name)
    return any(index['name'] == index_name for index in indexes)


# Kept around because a handful of migrations still import `text` from
# here transitively. Re-export to avoid breaking those.
__all__ = ['_has_table', '_table_has_column', 'index_exists', 'text']
