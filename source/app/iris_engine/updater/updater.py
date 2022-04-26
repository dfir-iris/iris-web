import requests
from packaging import version
import tempfile
from pathlib import Path
import gnupg


from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app import app, celery
from iris_interface import IrisInterfaceStatus as IStatus


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
        return True, None

    if releases.status_code == 200:
        releases_j = releases.json()

        return False, releases_j[0]

    if releases.status_code == 403:
        return True, releases.json()

    return True, None


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
        return False, release.get('message')

    release_version = release.get('name')

    if version.parse(current_version) < version.parse(release_version):
        return True, f'# New version {release_version} available\n\n{release.get("body")}', release

    else:
        return False, f'**Current server is up-to-date with {release_version}**', None


def init_server_update(release_config):
    log = []
    if not release_config:
        log.append('Release config is empty. Please contact IRIS team')
        return False, log

    log.append('Fetching release assets info')
    has_error, log_o, temp_dir = download_release_assets(release_config.get('assets'))
    log.extend(log_o)
    if has_error:
        log.append('Aborting upgrades - see previous errors')
        temp_dir.cleanup()
        return False, log

    has_error, log_o = verify_assets_signatures(temp_dir, release_config.get('assets'))
    log.extend(log_o)
    if has_error:
        log.append('Aborting upgrades - see previous errors')
        temp_dir.cleanup()
        return False, log

    return True, log


def verify_assets_signatures(target_directory, release_assets_info):
    # Expects a signature for every assets
    log = []
    has_error = False

    assets_check = {}

    for release_asset in release_assets_info:
        asset_name = release_asset.get('name')

        if not asset_name.endswith('.sig'):

            if (Path(target_directory.name) / asset_name).is_file():

                if (Path(target_directory.name) / f"{asset_name}.sig").is_file():
                    assets_check[Path(target_directory.name) / asset_name] = Path(target_directory.name) / f"{asset_name}.sig"

                else:
                    log.append(f"ERROR - {Path(target_directory.name) / asset_name} does not have a signature file")
                    has_error = True
            else:
                log.append(f"ERROR - Could not find {Path(target_directory.name) / asset_name}")
                has_error = True

    if has_error:
        return has_error, log

    log.append("Importing DFIR-IRIS GPG key from server")
    gpg = gnupg.GPG()

    with open('dependencies/DFIR-IRIS_pkey.asc', 'rb') as pkey:
        import_result = gpg.import_keys(pkey.read())

    if import_result.count < 1:
        log.append(f'ERROR - Unable to fetch {app.config.get("RELEASE_SIGNATURE_KEY")} from key server')
        has_error = True

    for asset in assets_check:
        with open(assets_check[asset], 'rb') as fin:

            verified = gpg.verify_file(fin, data_filename=asset)

            if not verified.valid:

                log.append(f'ERROR - {asset} does not have a valid signature (checked against {assets_check[asset]}). '
                           f'Contact DFIR-IRIS team')
                log.append(f"{verified.status}")
                has_error = True
                continue

            log.append(f"{asset} : signature validated")

    return has_error, log


def download_release_assets(release_assets_info):
    log = []
    has_error = False
    temp_dir = tempfile.TemporaryDirectory()

    for release_asset in release_assets_info:
        asset_name = release_asset.get('name')
        asset_url = release_asset.get('browser_download_url')

        # TODO: Check for available FS free space before downloading
        log.append(f'Downloading {asset_name} from {asset_url}')

        if not download_from_url(asset_url, Path(temp_dir.name) / asset_name):
            log.append('ERROR - Unable to save asset file to FS')
            has_error = True

    if has_error:
        log.append('Aborting upgrades - see previous errors')

    return has_error, log, temp_dir


def download_from_url(asset_url, target_file):

    with open(target_file, "wb") as file:
        response = get_external_url(asset_url)
        file.write(response.content)

    return Path(target_file).is_file()


@celery.task(bind=True)
def task_update_worker(self, update_to_version):
    celery.control.revoke(self.request.id)
    celery.control.broadcast("pool_restart", arguments={"reload_modules": True})

    return IStatus.I2Success(message="Pool restarted")
