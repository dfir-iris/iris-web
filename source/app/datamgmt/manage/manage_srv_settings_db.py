from app import db
from app.models import ServerSettings


def get_srv_settings():
    return ServerSettings.query.first()


def get_alembic_revision():
    with db.engine.connect() as con:
        version_num = con.execute("SELECT version_num FROM alembic_version").first()[0]
    return version_num or None
