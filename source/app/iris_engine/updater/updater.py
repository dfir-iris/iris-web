import requests
from packaging import version

from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app import app, celery
from iris_interface import IrisInterfaceStatus as IStatus


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


def is_updates_available():
    release = get_latest_release()
    current_version = app.config.get('IRIS_VERSION')

    release_version = release.get('name')

    if version.parse(current_version) < version.parse(release_version):
        return True, f'# New version {release_version} available\n\n{release.get("body")}'

    else:
        return False, f'**Current server is up-to-date with {release_version}**'


@celery.task(bind=True)
def task_update_worker(self, update_to_version):
    celery.control.revoke(self.request.id)
    celery.control.broadcast("pool_restart", arguments={"reload_modules": True})

    return IStatus.I2Success(message="Pool restarted")
