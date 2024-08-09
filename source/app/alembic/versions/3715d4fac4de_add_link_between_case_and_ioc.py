"""Add link between case and IOC

Revision ID: 3715d4fac4de
Revises: 9e4947a207a6
Create Date: 2024-05-22 16:33:24.146511

"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column, _has_table

# revision identifiers, used by Alembic.
revision = '3715d4fac4de'
down_revision = '11aa5b725b8e'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('ioc', 'case_id'):
        op.add_column(
            'ioc',
            sa.Column('case_id', sa.Integer, sa.ForeignKey('cases.case_id'), nullable=True)
        )

    # Migrate data
    if _has_table('ioc_link'):
        conn = op.get_bind()
        res = conn.execute(text(f"SELECT * FROM ioc_link;"))
        ioc_links = res.fetchall()

        for ioc_link in ioc_links:
            ioc = conn.execute(text("SELECT * FROM ioc WHERE ioc_id = :iocid"),
                               {'iocid': ioc_link.ioc_id}).fetchone()

            # If this link is already transferred to the IOC object
            if ioc.case_id and ioc.case_id == ioc_link.case_id:
                # We don't need to do anything
                pass

            # If this IOC is already linked to another case, we have to duplicate the object and related objects
            elif ioc.case_id and ioc.case_id != ioc_link.case_id:
                # Prevent duplication to happen multiple times
                check_exists = conn.execute(text("SELECT * FROM ioc WHERE ioc_value = :ioc_value AND ioc_type_id = :ioc_type_id AND case_id = :case_id"), {
                    "ioc_value": ioc.ioc_value, "ioc_type_id": ioc.ioc_type_id, "case_id": ioc_link.case_id
                }).fetchone()

                if check_exists:
                    continue

                # Duplicate IOC
                r = conn.execute(text(
                    "INSERT INTO ioc(ioc_value, ioc_type_id, ioc_description, ioc_tags, user_id, ioc_misp, ioc_tlp_id, custom_attributes, ioc_enrichment, modification_history, case_id)"
                    "VALUES (:ioc_value, :ioc_type_id, :ioc_description, :ioc_tags, :user_id, :ioc_misp, :ioc_tlp_id, :custom_attributes, :ioc_enrichment, :modification_history, :case_id)"
                    "RETURNING ioc_id"),
                    {
                        "ioc_value": ioc.ioc_value,
                        "ioc_type_id": ioc.ioc_type_id,
                        "ioc_description": ioc.ioc_description,
                        "ioc_tags": ioc.ioc_tags,
                        "user_id": ioc.user_id,
                        "ioc_misp": ioc.ioc_misp,
                        "ioc_tlp_id": ioc.ioc_tlp_id,
                        "custom_attributes": json.dumps(ioc.custom_attributes),
                        "ioc_enrichment": ioc.ioc_enrichment,
                        "modification_history": ioc.modification_history,
                        "case_id": ioc_link.case_id
                    }).fetchone()

                new_ioc_id = r.ioc_id

                # Duplicate comments
                comment_links = conn.execute(text("SELECT * FROM ioc_comments WHERE comment_ioc_id = :ioc_id"),
                                             {"ioc_id": ioc.ioc_id})

                # Deleting the old ioc_comments links
                conn.execute(text("DELETE FROM ioc_comments WHERE comment_ioc_id = :ioc_id"),
                                {"ioc_id": ioc.ioc_id})

                # Inserting the new comments
                for comment_link in comment_links:
                    comment = conn.execute(text("SELECT * FROM comments WHERE comment_id = :comment_id"),
                                           {"comment_id": comment_link.comment_id}).fetchone()
                    new_comment = conn.execute(text(
                        "INSERT INTO comments(comment_text, comment_date, comment_update_date, comment_user_id, comment_case_id, comment_alert_id)"
                        "VALUES (:comment_text, :comment_date, :comment_update_date, :comment_user_id, :comment_case_id, :comment_alert_id) "
                        "RETURNING comment_id"),
                        {
                            "comment_text": comment.comment_text,
                            "comment_date": comment.comment_date,
                            "comment_update_date": comment.comment_update_date,
                            "comment_user_id": comment.comment_user_id,
                            "comment_case_id": ioc_link.case_id,
                            "comment_alert_id": comment.comment_alert_id,
                        }).fetchone()
                    conn.execute(text("INSERT INTO ioc_comments(comment_id, comment_ioc_id) VALUES (:comment_id, :ioc_id)"),
                                 {"comment_id": new_comment.comment_id, "ioc_id": new_ioc_id})

                # duplicate assets
                asset_links = conn.execute(text("SELECT ioc_asset_link.asset_id FROM ioc_asset_link "
                                                "JOIN case_assets ON ioc_asset_link.asset_id = case_assets.asset_id "
                                                "WHERE ioc_id = :ioc_id AND case_id = :case_id "),
                                           {"ioc_id": ioc.ioc_id, "case_id": ioc_link.case_id})

                asset_ids = [row.asset_id for row in asset_links]

                if asset_ids:
                    delete_query = text("""
                        DELETE FROM ioc_asset_link 
                        WHERE asset_id IN :asset_ids
                    """)

                    # Execute the DELETE query
                    conn.execute(delete_query, {"asset_ids": tuple(asset_ids)})

                    # Inserting the new ioc_asset_link links
                    for asset_link in asset_ids:
                        conn.execute(text(
                            "INSERT INTO ioc_asset_link(ioc_id, asset_id)"
                            "VALUES (:ioc_id, :asset_id)"),
                            {
                                "ioc_id": new_ioc_id,
                                "asset_id": asset_link.asset_id,
                            })

                # duplicate case events ioc
                case_event_links = conn.execute(text("SELECT * FROM case_events_ioc WHERE ioc_id = :ioc_id AND case_id = :case_id"),
                                                {"ioc_id": ioc.ioc_id, "case_id": ioc_link.case_id})

                # Deleting the old case_event_ioc links
                conn.execute(text("DELETE FROM case_events_ioc WHERE ioc_id = :ioc_id AND case_id = :case_id"),
                             {"ioc_id": ioc.ioc_id, "case_id": ioc_link.case_id})

                # Inserting the new case_event_ioc links
                for case_event_link in case_event_links:
                    conn.execute(text(
                        "INSERT INTO case_events_ioc(case_event_id, ioc_id, case_id)"
                        "VALUES (:case_event_id, :ioc_id, :case_id)"),
                        {
                            "case_event_id": case_event_link.case_event_id,
                            "ioc_id": new_ioc_id,
                            "case_id": ioc_link.case_id
                        })


            # If there is no case id, we can set the case id
            else:
                conn.execute(text("UPDATE ioc SET case_id = :caseid WHERE ioc_id = :iocid"),
                             {'iocid': ioc.ioc_id, "caseid": ioc_link.case_id})

    # For backup options we leave the ioc_link for now
    # Drop old table
    # op.drop_table('ioc_link')

    op.alter_column('ioc', 'case_id', nullable=True)


def downgrade():
    pass
