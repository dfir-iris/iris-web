"""Add uniqueness to Tags table

Revision ID: 50f28953a485
Revises: c959c298ca00
Create Date: 2023-04-06 16:17:40.043545

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '50f28953a485'
down_revision = 'c959c298ca00'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Update the CaseTags table to point to the first tag with the same title
    conn.execute(text("""
        WITH duplicates AS (
            SELECT
                MIN(id) as min_id,
                tag_title
            FROM
                tags
            GROUP BY
                tag_title
            HAVING
                COUNT(*) > 1
        ),
        duplicate_tags AS (
            SELECT
                id,
                tag_title
            FROM
                tags
            WHERE
                tag_title IN (SELECT tag_title FROM duplicates)
        )
        UPDATE
            case_tags
        SET
            tag_id = duplicates.min_id
        FROM
            duplicates,
            duplicate_tags
        WHERE
            case_tags.tag_id = duplicate_tags.id
            AND duplicate_tags.tag_title = duplicates.tag_title
            AND duplicate_tags.id <> duplicates.min_id;
    """))

    # Remove duplicates in the tags table
    conn.execute(text("""
        DELETE FROM tags
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER()
                OVER (PARTITION BY tag_title ORDER BY id) AS rnum
                FROM tags) t
            WHERE t.rnum > 1);
    """))

    # Add the unique constraint to the tag_title column
    op.create_unique_constraint(None, 'tags', ['tag_title'])

    pass


def downgrade():
    pass
