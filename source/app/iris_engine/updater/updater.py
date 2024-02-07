#  IRIS Core Code
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import gnupg
import hashlib
import json
import os
import requests
import shutil
import subprocess
import tempfile
import time
from celery.schedules import crontab
from datetime import datetime
from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room
from packaging import version
from pathlib import Path

from app import app
from app import cache
from app import celery
from app import db
from app import socket_io
from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app.iris_engine.backup.backup import backup_iris_db
from app.models import ServerSettings
from iris_interface import IrisInterfaceStatus as IStatus

log = app.logger


def update_log_to_socket(status, is_error=False):
    log.info(status)
    data = {
        "message": status,
        "is_error": is_error
    }
    socket_io.emit('update_status', data, to='iris_update_status', namespace='/server-updates')


def notify_server_off():
    socket_io.emit('server_has_turned_off', {}, to='iris_update_status', namespace='/server-updates')


def notify_update_failed():
    socket_io.emit('update_has_fail', {}, to='iris_update_status', namespace='/server-updates')


def update_log(status):
    update_log_to_socket(status)


def update_log_error(status):
    update_log_to_socket(status, is_error=True)


@socket_io.on('join-update', namespace='/server-updates')
def get_message(data):

    room = data['channel']
    join_room(room=room)

    emit('join', {'message': f"{current_user.user} just joined", 'is_error': False}, room=room,
         namespace='/server-updates')


@socket_io.on('update_ping', namespace='/server-updates')
def socket_on_update_ping(msg):

    emit('update_ping', {'message': f"Server connected", 'is_error': False},
         namespace='/server-updates')


@socket_io.on('update_get_current_version', namespace='/server-updates')
def socket_on_update_do_reboot(msg):

    socket_io.emit('update_current_version', {"version": app.config.get('IRIS_VERSION')}, to='iris_update_status',
                   namespace='/server-updates')


def notify_server_ready_to_reboot():
    socket_io.emit('server_ready_to_reboot', {}, to='iris_update_status', namespace='/server-updates')


def notify_server_has_updated():
    socket_io.emit('server_has_updated', {}, to='iris_update_status', namespace='/server-updates')


def inner_init_server_update():
    has_updates, updates_content, release_config = is_updates_available()
    init_server_update(release_config)


def get_external_url(url):
    server_settings = get_server_settings_as_dict()
    proxies = server_settings.get('proxies')
    try:
        request = requests.get(url, proxies=proxies)
    except Exception as e:
        app.logger.error(e)
        return None

    return request


def get_latest_release():

    try:
        releases = get_external_url(app.config.get('RELEASE_URL'))
    except Exception as e:
        app.logger.error(e)
        return True, {'message': f"Unexpected error. {str(e)}"}

    if not releases:
        return True, {'message': "Unexpected error"}

    if releases.status_code == 200:
        releases_j = releases.json()

        return False, releases_j[0]

    if releases.status_code == 403:
        return True, releases.json()

    return True, {'msg': "Unexpected error"}


def get_release_assets(assets_url):

    try:
        release_assets = get_external_url(assets_url)
    except Exception as e:
        app.logger.error(e)
        return None

    if release_assets:
        return release_assets.json()

    return None


def is_updates_available():
    has_error, release = get_latest_release()

    current_version = app.config.get('IRIS_VERSION')

    if has_error:
        return False, release.get('message'), None

    release_version = release.get('name')

    cache.delete('iris_has_updates')

    srv_settings = ServerSettings.query.first()
    if not srv_settings:
        raise Exception('Unable to fetch server settings. Please reach out for help')

    if version.parse(current_version) < version.parse(release_version):
        srv_settings.has_updates_available = True
        db.session.commit()
        return True, f'# New version {release_version} available\n\n{release.get("body")}', release

    else:
        srv_settings.has_updates_available = False
        db.session.commit()
        return False, f'**Current server is up-to-date with {release_version}**', None


def init_server_update(release_config):

    if not release_config:
        update_log_error('Release config is empty. Please contact IRIS team')
        notify_update_failed()
        return False

    update_log('Fetching release assets info')
    has_error, temp_dir = download_release_assets(release_config.get('assets'))
    if has_error:
        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    has_error = verify_assets_signatures(temp_dir, release_config.get('assets'))
    if has_error:
        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    updates_config = verify_compatibility(temp_dir, release_config.get('assets'))
    if updates_config is None:
        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    update_archive = Path(temp_dir) / updates_config.get('app_archive')

    has_error = verify_archive_fingerprint(update_archive, updates_config.get('app_fingerprint'))
    if not has_error:
        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    update_log('Backing up current version')
    has_error = update_backup_current_version()
    if has_error:
        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    update_log('Backing up database')
    has_error, logs = backup_iris_db()
    if has_error:
        for log_entry in logs:
            update_log_error(log_entry)

        update_log_error('Aborting upgrades - see previous errors')
        notify_update_failed()
        shutil.rmtree(temp_dir)
        return False

    if 'worker' in updates_config.get('scope'):
        update_log('Worker needs to be updated. Scheduling updates task')
        async_update = task_update_worker.delay(update_archive.as_posix(), updates_config)

        update_log('Scheduled. Waiting for worker to finish updating')
        result_output = async_update.get(interval=1)
        if result_output.is_failure():
            update_log_error('Worker failed to updates')
            update_log_error(result_output.logs)

            update_log_error('Aborting upgrades - see previous errors')
            notify_update_failed()
            shutil.rmtree(temp_dir)
            return False

        time.sleep(5)
        async_update_version = task_update_get_version.delay()
        result_output = async_update_version.get(interval=1)
        if result_output.is_failure():
            update_log_error('Worker failed to updates')
            update_log_error(result_output.data)

            update_log_error('Aborting upgrades - see previous errors')
            notify_update_failed()
            shutil.rmtree(temp_dir)
            return False

        worker_update_version = result_output.get_data()
        if worker_update_version != updates_config.get('target_version'):
            update_log_error('Worker failed to updates')
            update_log_error(f'Expected version {updates_config.get("target_version")} but worker '
                             f'is in {worker_update_version}')
            update_log_error('Aborting upgrades - see previous errors')
            notify_update_failed()
            shutil.rmtree(temp_dir)
            return False

        update_log(f'Worker updated to {updates_config.get("target_version")}')

    if updates_config.get('need_app_reboot') is True:
        update_log('Closing all database connections. Unsaved work will be lost.')
        from sqlalchemy.orm import close_all_sessions
        close_all_sessions()

        update_log('All checks passed. IRIS will turn off shortly and updates')
        update_log('Please don\'t leave the page - logging will resume here')
        update_log('Handing off to updater')

        notify_server_off()
        time.sleep(0.5)

    if 'iriswebapp' in updates_config.get('scope'):

        if call_ext_updater(update_archive=update_archive, scope="iriswebapp",
                            need_reboot=updates_config.get('need_app_reboot')):

            socket_io.stop()

    return True


def verify_archive_fingerprint(update_archive, archive_sha256):
    update_log('Verifying updates archive')
    if update_archive.is_file():
        sha256_hash = hashlib.sha256()

        with open(update_archive, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        current_sha256 = sha256_hash.hexdigest().upper()
        if current_sha256 == archive_sha256:
            return True

        update_log_error(f'Fingerprint mismatch. Expected {archive_sha256} but got {current_sha256}')

    else:
        update_log_error(f'Archive {update_archive} not found')

    return False


def call_ext_updater(update_archive, scope, need_reboot):
    if not isinstance(update_archive, Path):
        update_archive = Path(update_archive)

    archive_name = Path(update_archive).stem

    if os.getenv("DOCKERIZED"):
        source_dir = Path.cwd() / 'scripts'
        target_dir = Path.cwd()
        docker = 1
    else:
        source_dir = Path.cwd().absolute() / 'scripts'
        if app.config["DEVELOPMENT"]:
            target_dir = Path('../../update_server/test_update')
        else:
            target_dir = Path.cwd()

        docker = 0

    try:

        subprocess.Popen(["/bin/bash", f"{source_dir}/iris_updater.sh",
                          update_archive.as_posix(),        # Update archive to unpack
                          target_dir.as_posix(),            # Target directory of update
                          archive_name,                     # Root directory of the archive
                          scope[0],                        # Scope of the update
                          '1' if docker else '0',                           # Are we in docker ?
                          '1' if need_reboot else '0',                      # Do we need to restart the app
                          '&'])

    except Exception as e :
        log.error(str(e))
        return False

    return True


def update_backup_current_version():
    date_time = datetime.now()

    root_backup = Path(app.config.get("BACKUP_PATH"))
    root_backup.mkdir(exist_ok=True)

    backup_dir = root_backup / f"server_backup_{date_time.timestamp()}"
    backup_dir.mkdir(exist_ok=True)
    if not backup_dir.is_dir():
        update_log_error(f"Unable to create directory {backup_dir} for backup. Aborting")
        return True

    if os.getenv("DOCKERIZED"):
        source_dir = Path.cwd()
    else:
        source_dir = Path.cwd().parent.absolute()

    try:
        update_log(f'Copying {source_dir} to {backup_dir}')
        shutil.copytree(source_dir, backup_dir, dirs_exist_ok=True)
    except Exception as e:
        update_log_error('Unable to backup current version')
        update_log_error(str(e))
        return False, ['Unable to backup current version', str(e)]

    update_log('Current version backed up')
    has_error = generate_backup_config_file(backup_dir)
    if has_error:
        return True

    return False


def generate_backup_config_file(backup_dir):
    backup_config = {
        "backup_date": datetime.now().timestamp(),
        "backup_version": app.config.get('IRIS_VERSION')
    }

    hashes_map = {}

    for entry in backup_dir.rglob('*'):

        if entry.is_file():
            sha256_hash = hashlib.sha256()

            with open(entry, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            hashes_map[entry.as_posix()] = sha256_hash.hexdigest()

    backup_config["hashes_map"] = hashes_map

    try:

        with open(backup_dir / "backup_config.json", 'w') as fconfig:
            json.dump(backup_config, fconfig, indent=4)

    except Exception as e:
        update_log_error('Unable to save configuration file')
        update_log_error(str(e))
        return True

    update_log('Backup configuration file generated')
    return False


def verify_compatibility(target_directory, release_assets_info):
    release_updates = None

    update_log('Verifying updates compatibilities')

    for release_asset in release_assets_info:
        asset_name = release_asset.get('name')
        if asset_name != 'release_updates.json':
            continue

        if (Path(target_directory) / asset_name).is_file():
            release_updates = Path(target_directory) / asset_name
            break

    if not release_updates:
        update_log_error('Unable to find release updates configuration file')
        return None

    try:
        with open(file=release_updates) as fin:
            updates_info = json.load(fin)
    except Exception as e:
        update_log_error('Unable to read release updates configuration file')
        update_log_error(str(e))
        update_log_error('Please contact DFIR-IRIS team')
        return None

    can_update = False
    accepted_versions = updates_info.get('accepted_versions')
    for av in accepted_versions:
        if version.parse(app.config.get('IRIS_VERSION')) == version.parse(av):
            can_update = True
            break

    if not can_update:
        update_log_error(f'Current version {app.config.get("IRIS_VERSION")} cannot '
                         f'be updated to {updates_info.get("target_version")} automatically')
        update_log_error(f'Supported versions are {updates_info.get("accepted_versions")}')
        return None

    if not updates_info.get('support_auto'):
        update_log_error(f'This updates does not support automatic handling. Please read the upgrades instructions.')
        return None

    if 'worker' not in updates_info.get('scope') and 'iriswebapp' not in updates_info.get('scope'):
        update_log_error(f'Something is wrong, updates configuration does not have any valid scope')
        update_log_error('Please contact DFIR-IRIS team')
        return None

    update_log('Compatibly checks done. Good to go')

    return updates_info


def verify_assets_signatures(target_directory, release_assets_info):
    # Expects a signature for every assets
    has_error = False

    assets_check = {}

    for release_asset in release_assets_info:
        asset_name = release_asset.get('name')

        if not asset_name.endswith('.sig'):

            if (Path(target_directory) / asset_name).is_file():

                if (Path(target_directory) / f"{asset_name}.sig").is_file():
                    assets_check[Path(target_directory) / asset_name] = Path(target_directory) / f"{asset_name}.sig"

                else:
                    update_log_error(f"{asset_name} does not have a signature file")
                    has_error = True
            else:
                update_log_error(f"Could not find {Path(target_directory) / asset_name}")
                has_error = True

    if has_error:
        return has_error

    update_log("Importing DFIR-IRIS GPG key")
    gpg = gnupg.GPG()

    with open(app.config.get("RELEASE_SIGNATURE_KEY"), 'rb') as pkey:
        import_result = gpg.import_keys(pkey.read())

    if import_result.count < 1:
        update_log_error(f'Unable to fetch {app.config.get("RELEASE_SIGNATURE_KEY")}')
        has_error = True

    for asset in assets_check:
        with open(assets_check[asset], 'rb') as fin:

            verified = gpg.verify_file(fin, data_filename=asset)

            if not verified.valid:

                update_log_error(f'{asset.name} does not have a valid signature (checked '
                                 f'against {assets_check[asset].name}). '
                                 f'Contact DFIR-IRIS team')
                update_log_error(f"Signature status : {verified.status}")
                has_error = True
                continue

            update_log(f"{asset.name} : signature validated")

    return has_error


def download_release_assets(release_assets_info):
    has_error = False
    if not Path(app.config.get("UPDATES_PATH")).is_dir():
        Path(app.config.get("UPDATES_PATH")).mkdir(exist_ok=True)

    temp_dir = tempfile.mkdtemp(dir=app.config.get("UPDATES_PATH"))

    for release_asset in release_assets_info:
        asset_name = release_asset.get('name')
        asset_url = release_asset.get('browser_download_url')

        # TODO: Check for available FS free space before downloading
        update_log(f'Downloading from {asset_url} to {temp_dir}')

        if not download_from_url(asset_url, Path(temp_dir) / asset_name):
            update_log_error('ERROR - Unable to save asset file to FS')
            has_error = True

    if has_error:
        update_log_error('Aborting upgrades - see previous errors')

    return has_error, temp_dir


def download_from_url(asset_url, target_file):

    with open(target_file, "wb") as file:
        response = get_external_url(asset_url)
        file.write(response.content)

    return Path(target_file).is_file()


@celery.task(bind=True)
def task_update_worker(self, update_archive, updates_config):

    if not call_ext_updater(update_archive=update_archive, scope="worker",
                            need_reboot=updates_config.get('need_worker_reboot')):

        return IStatus.I2Success(message="Unable to spawn updater")

    return IStatus.I2Success(message="Worker updater called")


@celery.task(bind=True)
def task_update_get_version(self):
    return IStatus.I2Success(data=app.config.get('IRIS_VERSION'))


@celery.on_after_finalize.connect
def setup_periodic_update_checks(self, **kwargs):
    self.add_periodic_task(
        crontab(hour=0, minute=0),
        task_check_available_updates.s(),
        name='iris_auto_check_updates'
    )


def remove_periodic_update_checks():
    if 'iris_auto_check_updates' in celery.conf['beat_schedule']:
        del celery.conf['beat_schedule']['iris_auto_check_updates']


@celery.task
def task_check_available_updates():
    log.info('Cron - Checking if updates are available')
    has_updates, _, _ = is_updates_available()
    srv_settings = ServerSettings.query.first()
    if not srv_settings:
        return IStatus.I2Error('Unable to fetch server settings. Please reach out for help')

    srv_settings.has_updates_available = has_updates
    db.session.commit()

    if srv_settings.has_updates_available:
        log.info('Updates are available for this server')

    return IStatus.I2Success(f'Successfully checked updates. Available : {srv_settings.has_updates_available}')
