"""Add namespace to tags

Revision ID: e0df2de997cc
Revises: d207b4d13385
Create Date: 2023-12-30 09:24:32.991449

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column
from app.datamgmt.manage.manage_tags_db import add_db_tag

# revision identifiers, used by Alembic.
revision = 'e0df2de997cc'
down_revision = 'd207b4d13385'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('tags', 'tag_namespace'):
        # Add namespace if it doesn't exist
        op.add_column('tags', sa.Column('tag_namespace', sa.Text(), nullable=True))

    tags = set()
    # Parse all tags from iocs and register them into tags if they don't exists
    ioc_tags = op.get_bind().execute("SELECT ioc_tags FROM ioc;").fetchall()
    for entry in ioc_tags:
        for ioc_tag in entry[0].split(',') if entry else []:
            tags.add(ioc_tag.strip())

    # Parse all tags from assets and register them into tags if they don't exists
    asset_tags = op.get_bind().execute("SELECT asset_tags FROM case_assets;").fetchall()
    for entry in asset_tags:
        for asset_tag in entry[0].split(',') if entry else []:
            tags.add(asset_tag.strip())

    # Parse all tags from case tasks and register them into tags if they don't exists
    task_tags = op.get_bind().execute("SELECT task_tags FROM case_tasks;").fetchall()
    for entry in task_tags:
        for task_tag in entry[0].split(',') if entry else []:
            tags.add(task_tag.strip())

    # Parse all tags from events and register them into tags if they don't exists
    event_tags = op.get_bind().execute("SELECT event_tags FROM cases_events;").fetchall()
    for entry in event_tags:
        for event_tag in entry[0].split(',') if entry else []:
            tags.add(event_tag.strip())

    # Add all tags to the database if they don't exist
    for tag in tags:
        add_db_tag(tag)

    pass


def downgrade():
    pass
