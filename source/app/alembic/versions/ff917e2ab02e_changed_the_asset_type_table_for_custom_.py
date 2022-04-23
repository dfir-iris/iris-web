"""changed the asset_type table for custom icons

Revision ID: ff917e2ab02e
Revises: b664ca1203a4
Create Date: 2022-04-21 22:14:55.815983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff917e2ab02e'
down_revision = 'b664ca1203a4'
branch_labels = None
depends_on = None

from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection


def upgrade():
    if not _table_has_column('asset_type', 'asset_icon_not_compromised'):
        op.add_column('asset_type',
                      sa.Column('asset_icon_not_compromised', sa.String(255))
                      )

        
    if not _table_has_column('asset_type', 'asset_icon_compromised'):
        op.add_column('asset_type',
                      sa.Column('asset_icon_compromised', sa.String(255))
                      )

    t_ua = sa.Table(
        'asset_type',
        sa.MetaData(),
        sa.Column('asset_id', sa.Integer, primary_key=True),
        sa.Column('asset_name', sa.String(155))
    )
    conn = op.get_bind()
    vals = t_ua.select()
    icon_not_compromised, icon_compromised = _get_icons(vals.assed_name)
    conn.execute(t_ua.update().values(
        asset_icon_not_compromised=icon_not_compromised,
        asset_icon_compromised=icon_compromised
    ))


def downgrade():
    pass

def _table_has_column(table, column):
    config = op.get_context().config
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.')
    insp = reflection.Inspector.from_engine(engine)
    has_column = False

    for col in insp.get_columns(table):
        if column != col['name']:
            continue
        has_column = True
    return has_column

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