"""Add link between case and IOC

Revision ID: 3715d4fac4de
Revises: 11aa5b725b8e
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
    # Add case_id column on ioc if it does not exist
    if not _table_has_column('ioc', 'case_id'):
        op.add_column(
            'ioc',
            sa.Column('case_id', sa.Integer, sa.ForeignKey('cases.case_id'), nullable=True)
        )

        op.execute("COMMIT")

    conn = op.get_bind()

    # If there's no ioc_link table, nothing to migrate
    if not _has_table('ioc_link'):
        op.alter_column('ioc', 'case_id', nullable=True)
        return


    # Fetch all ioc_link rows
    ioc_links = conn.execute(text("SELECT ioc_id, case_id FROM ioc_link")).fetchall()
    if not ioc_links:
        # Nothing to migrate
        op.alter_column('ioc', 'case_id', nullable=True)
        return

    # Collect all IOC IDs from ioc_link
    all_ioc_ids = {row.ioc_id for row in ioc_links}

    # Fetch all IOCs that appear in ioc_link
    #   We'll store them in a dict { ioc_id: {...} }
    iocs_data = conn.execute(
        text(
            """
            SELECT ioc_id, ioc_value, ioc_type_id, ioc_description, ioc_tags, user_id,
                   ioc_misp, ioc_tlp_id, custom_attributes, ioc_enrichment,
                   modification_history, case_id
              FROM ioc
             WHERE ioc_id = ANY(:ioc_ids)
            """
        ),
        {"ioc_ids": list(all_ioc_ids)},
    ).fetchall()

    iocs_dict = {}
    for row in iocs_data:
        iocs_dict[row.ioc_id] = dict(row._mapping)

    # Build a quick-lookup “existing iocs by (value, type, case_id)” for duplication checks
    # This includes *all* IOCs in the DB, not just those in ioc_link.
    # Because if the user has already inserted an IOC with the same value, type, and case,
    # we want to skip creating another duplicate.
    all_iocs = conn.execute(text("SELECT ioc_id, ioc_value, ioc_type_id, case_id FROM ioc")).fetchall()
    existing_map = {}
    # existing_map[(ioc_value, ioc_type_id, case_id)] = ioc_id
    for row in all_iocs:
        existing_map[(row.ioc_value, row.ioc_type_id, row.case_id)] = row.ioc_id

    # ioc_comments referencing these iocs
    ioc_comments_data = conn.execute(
        text(
            """
            SELECT comment_id, comment_ioc_id
              FROM ioc_comments
             WHERE comment_ioc_id = ANY(:ioc_ids)
            """
        ),
        {"ioc_ids": list(all_ioc_ids)},
    ).fetchall()
    comments_by_ioc = {}
    for row in ioc_comments_data:
        ioc_id = row.comment_ioc_id
        comments_by_ioc.setdefault(ioc_id, []).append(dict(row._mapping))

    # Now fetch the actual comments
    all_comment_ids = {c["comment_id"] for ioc_id in comments_by_ioc for c in comments_by_ioc[ioc_id]}
    if all_comment_ids:
        comments_data = conn.execute(
            text(
                """
                SELECT comment_id, comment_text, comment_date, comment_update_date,
                       comment_user_id, comment_case_id, comment_alert_id
                  FROM comments
                 WHERE comment_id = ANY(:comment_ids)
                """
            ),
            {"comment_ids": list(all_comment_ids)},
        ).fetchall()
        comments_dict = {}
        for row in comments_data:
            comments_dict[row.comment_id] = dict(row._mapping)
    else:
        comments_dict = {}

    # ioc_asset_link for these iocs (only those that also exist in case_assets)
    ioc_asset_data = conn.execute(
        text(
            """
            SELECT ial.ioc_id, ial.asset_id
              FROM ioc_asset_link ial
                   JOIN case_assets ca ON ial.asset_id = ca.asset_id
             WHERE ial.ioc_id = ANY(:ioc_ids)
            """
        ),
        {"ioc_ids": list(all_ioc_ids)},
    ).fetchall()
    assets_by_ioc = {}
    for row in ioc_asset_data:
        ioc_id = row.ioc_id
        assets_by_ioc.setdefault(ioc_id, []).append(row.asset_id)

    # case_events_ioc for these iocs
    ioc_events_data = conn.execute(
        text(
            """
            SELECT event_id, ioc_id, case_id
              FROM case_events_ioc
             WHERE ioc_id = ANY(:ioc_ids)
            """
        ),
        {"ioc_ids": list(all_ioc_ids)},
    ).fetchall()
    events_by_ioc_and_case = {}
    for row in ioc_events_data:
        ioc_id = row.ioc_id
        case_id = row.case_id
        events_by_ioc_and_case.setdefault((ioc_id, case_id), []).append(row.event_id)


    # We'll keep track of which (ioc_id, case_id) pairs we've already handled
    # so we don't do duplicate work if multiple ioc_link rows refer to the same pair.
    already_handled = set()

    for link in ioc_links:
        ioc_id = link.ioc_id
        link_case_id = link.case_id

        if (ioc_id, link_case_id) in already_handled:
            # We've already processed duplication or update for this combination.
            continue
        already_handled.add((ioc_id, link_case_id))

        # If for some reason the ioc doesn't exist (shouldn't happen), skip
        if ioc_id not in iocs_dict:
            continue

        ioc_row = iocs_dict[ioc_id]
        current_case_id = ioc_row["case_id"]

        # If the IOC is already linked to the same case, do nothing
        if current_case_id == link_case_id:
            continue

        # If the IOC has no case_id, just set it
        if current_case_id is None:
            # Single update for this IOC
            update_case_query = text(
                """
                UPDATE ioc
                   SET case_id = :case_id
                 WHERE ioc_id = :ioc_id
                """
            )
            conn.execute(update_case_query, {"ioc_id": ioc_id, "case_id": link_case_id})
            ioc_row["case_id"] = link_case_id
            # We are done with this link
            continue

        # If the IOC is already linked to a different case_id => we do the "duplicate" logic
        if current_case_id != link_case_id:
            # Check our in-memory map of existing iocs to see if the (value, type, link_case_id) is present
            key = (ioc_row["ioc_value"], ioc_row["ioc_type_id"], link_case_id)
            if key in existing_map:
                # Already have an IOC with these (value, type, case). Skip duplication
                continue

            # Duplicate the IOC
            insert_ioc_query = text(
                """
                INSERT INTO ioc (
                    ioc_value, ioc_type_id, ioc_description, ioc_tags, user_id,
                    ioc_misp, ioc_tlp_id, custom_attributes, ioc_enrichment,
                    modification_history, case_id
                )
                VALUES (
                    :ioc_value, :ioc_type_id, :ioc_description, :ioc_tags, :user_id,
                    :ioc_misp, :ioc_tlp_id, :custom_attributes, :ioc_enrichment,
                    :modification_history, :case_id
                )
                RETURNING ioc_id
                """
            )
            new_ioc = conn.execute(
                insert_ioc_query,
                {
                    "ioc_value": ioc_row["ioc_value"],
                    "ioc_type_id": ioc_row["ioc_type_id"],
                    "ioc_description": ioc_row["ioc_description"],
                    "ioc_tags": ioc_row["ioc_tags"],
                    "user_id": ioc_row["user_id"],
                    "ioc_misp": ioc_row["ioc_misp"],
                    "ioc_tlp_id": ioc_row["ioc_tlp_id"],
                    "custom_attributes": json.dumps(ioc_row["custom_attributes"]),
                    "ioc_enrichment": json.dumps(ioc_row["ioc_enrichment"]),
                    "modification_history": json.dumps(ioc_row["modification_history"]),
                    "case_id": link_case_id,
                },
            ).fetchone()
            new_ioc_id = new_ioc.ioc_id

            # Update our global in-memory map so future checks won't create a second duplicate
            existing_map[key] = new_ioc_id


            # Move ioc_comments to the new ioc
            if ioc_id in comments_by_ioc:
                old_comment_links = comments_by_ioc[ioc_id]
                # Avoid repeated move attempts if we see this ioc again
                comments_by_ioc[ioc_id] = []

                # Delete links from the old ioc
                conn.execute(
                    text("DELETE FROM ioc_comments WHERE comment_ioc_id = :old_ioc_id"),
                    {"old_ioc_id": ioc_id},
                )

                # For each old link, create a brand-new comment, then link it
                insert_comment_query = text(
                    """
                    INSERT INTO comments(
                        comment_text, comment_date, comment_update_date,
                        comment_user_id, comment_case_id, comment_alert_id
                    )
                    VALUES (
                        :comment_text, :comment_date, :comment_update_date,
                        :comment_user_id, :comment_case_id, :comment_alert_id
                    )
                    RETURNING comment_id
                    """
                )
                link_comment_query = text(
                    """
                    INSERT INTO ioc_comments(comment_id, comment_ioc_id)
                    VALUES (:comment_id, :new_ioc_id)
                    """
                )
                for c_link in old_comment_links:
                    old_comment = comments_dict.get(c_link["comment_id"])
                    if not old_comment:
                        continue

                    new_comment = conn.execute(
                        insert_comment_query,
                        {
                            "comment_text": old_comment["comment_text"],
                            "comment_date": old_comment["comment_date"],
                            "comment_update_date": old_comment["comment_update_date"],
                            "comment_user_id": old_comment["comment_user_id"],
                            # tie it to the new case
                            "comment_case_id": link_case_id,
                            "comment_alert_id": old_comment["comment_alert_id"],
                        },
                    ).fetchone()

                    # Link new comment to the duplicated ioc
                    conn.execute(
                        link_comment_query,
                        {"comment_id": new_comment.comment_id, "new_ioc_id": new_ioc_id},
                    )

            # Move assets
            if ioc_id in assets_by_ioc and assets_by_ioc[ioc_id]:
                old_asset_ids = assets_by_ioc[ioc_id]
                assets_by_ioc[ioc_id] = []  # prevent re-processing

                # Remove the old links
                conn.execute(
                    text(
                        """
                        DELETE FROM ioc_asset_link
                         WHERE ioc_id = :old_ioc_id
                           AND asset_id = ANY(:asset_ids)
                        """
                    ),
                    {"old_ioc_id": ioc_id, "asset_ids": list(old_asset_ids)},
                )

                # Insert new links
                insert_asset_link_query = text(
                    "INSERT INTO ioc_asset_link(ioc_id, asset_id) VALUES (:new_ioc_id, :asset_id)"
                )
                for aid in old_asset_ids:
                    conn.execute(
                        insert_asset_link_query, {"new_ioc_id": new_ioc_id, "asset_id": aid}
                    )

            # Move case_events_ioc
            old_events = events_by_ioc_and_case.get((ioc_id, link_case_id), [])
            if old_events:
                events_by_ioc_and_case[(ioc_id, link_case_id)] = []  # prevent re-processing
                conn.execute(
                    text(
                        """
                        DELETE FROM case_events_ioc
                         WHERE ioc_id = :old_ioc_id
                           AND case_id = :old_case_id
                        """
                    ),
                    {"old_ioc_id": ioc_id, "old_case_id": link_case_id},
                )
                insert_case_events_query = text(
                    """
                    INSERT INTO case_events_ioc(event_id, ioc_id, case_id)
                    VALUES (:event_id, :ioc_id, :case_id)
                    """
                )
                for ev_id in old_events:
                    conn.execute(
                        insert_case_events_query,
                        {"event_id": ev_id, "ioc_id": new_ioc_id, "case_id": link_case_id},
                    )

    # op.drop_table('ioc_link')

    # Finally, ensure case_id is nullable or not as needed.
    op.alter_column('ioc', 'case_id', nullable=True)


def downgrade():
    pass
