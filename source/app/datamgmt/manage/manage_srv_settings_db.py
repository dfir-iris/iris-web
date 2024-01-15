from sqlalchemy import text

from app import db
from app.models import ServerSettings
from app.schema.marshables import ServerSettingsSchema


def get_srv_settings():
    return ServerSettings.query.first()


def get_server_settings_as_dict():
    srv_settings = ServerSettings.query.first()
    if srv_settings:

        sc = ServerSettingsSchema()
        return sc.dump(srv_settings)

    else:
        return {}


def get_alembic_revision():
    with db.engine.connect() as con:
        version_num = con.execute(text("SELECT version_num FROM alembic_version")).first()[0]
    return version_num or None
