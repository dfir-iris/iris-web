"""Add namespace to tags

Revision ID: e0df2de997cc
Revises: d207b4d13385
Create Date: 2023-12-30 09:24:32.991449

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

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
    ioc_tags = op.get_bind().execute(text("SELECT ioc_tags FROM ioc;")).fetchall()
    for entry in ioc_tags:
        for ioc_tag in entry[0].split(',') if entry[0] else []:
            ioc_tag = ioc_tag.strip()
            if ioc_tag:
                tags.add(ioc_tag)

    # Parse all tags from assets and register them into tags if they don't exists
    asset_tags = op.get_bind().execute(text("SELECT asset_tags FROM case_assets;")).fetchall()
    for entry in asset_tags:
        for asset_tag in entry[0].split(',') if entry[0] else []:
            asset_tag = asset_tag.strip()
            if asset_tag:
                tags.add(asset_tag.strip())

    # Parse all tags from case tasks and register them into tags if they don't exists
    task_tags = op.get_bind().execute(text("SELECT task_tags FROM case_tasks;")).fetchall()
    for entry in task_tags:
        for task_tag in entry[0].split(',') if entry[0] else []:
            task_tag = task_tag.strip()
            if task_tag:
                tags.add(task_tag.strip())

    # Parse all tags from events and register them into tags if they don't exists
    event_tags = op.get_bind().execute(text("SELECT event_tags FROM cases_events;")).fetchall()
    for entry in event_tags:
        for event_tag in entry[0].split(',') if entry[0] else []:
            event_tag = event_tag.strip()
            if event_tag:
                tags.add(event_tag.strip())

    if len(tags) > 0:
        # Bulk add all tags with a RAW SQL query and skip error if tag already exists
        op.get_bind().execute(text("INSERT INTO tags (tag_title) VALUES (:tag_title) ON CONFLICT (tag_title) DO NOTHING"),
                              [{"tag_title": tag} for tag in tags])

    pass


def downgrade():
    pass
