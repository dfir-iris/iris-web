"""changed the assets_type table for custom icons

Revision ID: ff917e2ab02e
Revises: c832bd69f827
Create Date: 2022-04-21 22:14:55.815983

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = 'ff917e2ab02e'
down_revision = 'c832bd69f827'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('assets_type', 'asset_icon_not_compromised'):
        op.add_column('assets_type',
                      sa.Column('asset_icon_not_compromised', sa.String(255))
                      )

    if not _table_has_column('assets_type', 'asset_icon_compromised'):
        op.add_column('assets_type',
                      sa.Column('asset_icon_compromised', sa.String(255))
                      )

    t_assets_type = sa.Table(
        'assets_type',
        sa.MetaData(),
        sa.Column('asset_id', sa.Integer, primary_key=True),
        sa.Column('asset_name', sa.String(155)),
        sa.Column('asset_icon_not_compromised', sa.String(255)),
        sa.Column('asset_icon_compromised', sa.String(255))
    )
    
    # Migrate existing Asset_types
    conn = op.get_bind()
    res = conn.execute(text("SELECT asset_id, asset_name FROM public.assets_type;"))
    results = res.fetchall()

    if results:
        for res in results:
            icon_not_compromised, icon_compromised = _get_icons(res[1])
            conn.execute(t_assets_type.update().where(t_assets_type.c.asset_id == res[0]).values(
                asset_icon_not_compromised=icon_not_compromised,
                asset_icon_compromised=icon_compromised
            ))


def downgrade():
    pass


def _get_icons(asset_name):
    assets = {
        "Account": ("Generic Account", "user.png", "ioc_user.png"),
        "Firewall": ("Firewall", "firewall.png", "ioc_firewall.png"),
        "Linux - Server": ("Linux server", "server.png", "ioc_server.png"),
        "Linux - Computer": ("Linux computer", "desktop.png", "ioc_desktop.png"),
        "Linux Account": ("Linux Account", "user.png", "ioc_user.png"),
        "Mac - Computer": ("Mac computer", "desktop.png", "ioc_desktop.png"),
        "Phone - Android": ("Android Phone", "phone.png", "ioc_phone.png"),
        "Phone - IOS": ("Apple Phone", "phone.png", "ioc_phone.png"),
        "Windows - Computer": ("Standard Windows Computer", "windows_desktop.png", "ioc_windows_desktop.png"),
        "Windows - Server": ("Standard Windows Server", "windows_server.png", "ioc_windows_server.png"),
        "Windows - DC": ("Domain Controller", "windows_server.png", "ioc_windows_server.png"),
        "Router": ("Router", "router.png", "ioc_router.png"),
        "Switch": ("Switch", "switch.png", "ioc_switch.png"),
        "VPN": ("VPN", "vpn.png", "ioc_vpn.png"),
        "WAF": ("WAF", "firewall.png", "ioc_firewall.png"),
        "Windows Account - Local": ("Windows Account - Local", "user.png", "ioc_user.png"),
        "Windows Account - Local - Admin": ("Windows Account - Local - Admin", "user.png", "ioc_user.png"),
        "Windows Account - AD": ("Windows Account - AD", "user.png", "ioc_user.png"),
        "Windows Account - AD - Admin": ("Windows Account - AD - Admin", "user.png", "ioc_user.png"),
        "Windows Account - AD - krbtgt": ("Windows Account - AD - krbtgt", "user.png", "ioc_user.png"),
        "Windows Account - AD - Service": ("Windows Account - AD - krbtgt", "user.png", "ioc_user.png")
    }
    if assets.get(asset_name):
        return assets.get(asset_name)[1], assets.get(asset_name)[2]
    else:
        return "question-mark.png","ioc_question-mark.png"