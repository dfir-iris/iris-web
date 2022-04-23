import requests

from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app import app


def get_latest_release():
    server_settings = get_server_settings_as_dict()
    proxies = server_settings.get('proxies')
    try:
        releases = requests.get(app.config.get('RELEASE_URL'), proxies=proxies)
    except Exception as e:
        app.logger.error(e)
        return None

    if releases:
        releases_j = releases.json()
        return releases_j[0]

    return None