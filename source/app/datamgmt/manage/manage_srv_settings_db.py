from app import db
from app.models import ServerSettings


def get_srv_settings():
    return ServerSettings.query.first()

