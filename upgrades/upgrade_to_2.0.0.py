#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRS
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

import argparse
import logging as log
from pathlib import Path

root_dir = Path(__file__).parent.parent

LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
LOG_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

log.basicConfig(level=log.INFO, format=LOG_FORMAT, datefmt=LOG_TIME_FORMAT)

env_upgrade_map = {
    "DB_USER": "POSTGRES_ADMIN_USER",
    "DB_PASS": "POSTGRES_ADMIN_PASSWORD",
    "DB_HOST": "POSTGRES_SERVER",
    "DB_PORT": "POSTGRES_PORT",
    "SECRET_KEY": "IRIS_SECRET_KEY",
    "SECURITY_PASSWORD_SALT": "IRIS_SECURITY_PASSWORD_SALT",
    "APP_HOST": "IRIS_UPSTREAM_SERVER",
    "APP_PORT": "IRIS_UPSTREAM_PORT",
    "IRIS_WORKER": "#IRIS_WORKER"
}


class IrisUpgrade200:

    @staticmethod
    def handle_ports(content):
        if 'INTERFACE_HTTPS_PORT' not in content:
            log.info('What port do you want to use for HTTPS?')
            port = input()
            content += f"\n\n#IRIS Ports\nINTERFACE_HTTPS_PORT={port}"

        return content

    def handle_env(self, dry_run=False):
        with open(root_dir / '.env', "r") as f:
            content = f.read()

            for old, new in env_upgrade_map.items():
                if f"{old}=" not in content:
                    continue

                if f"{new}=" in content:
                    log.info(f'{new} already set. Skipping')
                    continue

                if dry_run:
                    log.info(f'Would have replaced {old} with {new}')
                else:
                    log.info(f'Replacing {old} with {new}')
                    content = content.replace(f"{old}=", f"{new}=")

        if "IRIS_WORKER=1" in content:
            if dry_run:
                log.info('Would have disabled old IRIS_WORKER')
            else:
                log.info('Old IRIS_WORKER is set. Disabling')
                content = content.replace("IRIS_WORKER=1", "#IRIS_WORKER=0")

        if "IRIS_AUTHENTICATION_METHOD=" not in content:
            if dry_run:
                log.info('Would have added IRIS_AUTHENTICATION_METHOD to .env file')
            else:
                log.info('Adding IRIS_AUTHENTICATION_METHOD to .env file')
                content += f"\n\n#IRIS Authentication\nIRIS_AUTHENTICATION_METHOD=local"

        log.warning('IRIS v2.0.0 changed the default listening port from 4433 to 443.')
        log.info('Do you want to change the port? (y/n)')
        answer = input()
        if answer.lower() == "y":
            content = self.handle_ports(content)

        log.info("IRIS v2.0.0 comes with new features. The following is optional.")
        log.info("Do you want to set the organization name? (y/n)")
        answer = input()
        if answer.lower() == "y":
            log.info("Please enter the organization name:")
            organization_name = input()
            if "IRIS_ORGANIZATION_NAME=" in content:
                log.info("IRIS_ORGANIZATION_NAME already set. Replacing it.")
                content = content.replace(f"IRIS_ORGANIZATION_NAME=", "#IRIS_ORGANIZATION_NAME=")

            content += f"\n\n#IRIS Organization\nIRIS_ORGANIZATION_NAME={organization_name}"

        if not dry_run:
            log.info('Writing new .env file')
            with open(root_dir / '.env', "w") as f:
                f.write(content)

        else:
            log.info('Dry run: would have written new .env file')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n')
            print(content)
            print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')

    def upgrade(self, dry_run=False):
        """
        Upgrade IRIS to 2.0.0
        """
        if not self.check(silent=True):
            log.info('Upgrade aborted')
            return False

        log.info('Checking .env file')
        self.handle_env(dry_run=dry_run)

        log.info('Upgrade done. Please check the changes. ')
        log.info('You can now rebuild the dockers with `docker compose build --no-cache`')
        log.info('And start them with `docker compose up`')

    @staticmethod
    def check(silent=False):
        """
        Check if upgrade looks doable
        """
        if not (root_dir / '.env').exists():
            log.error(f'No .env file found in {root_dir}')
            log.info('You can create one with the following command: cp .env.model .env')
            log.info('Then edit it to match your criteria')
            log.info('You do not need to run this script to upgrade to 2.0.0')
            return False

        with open(root_dir / '.env', "r") as f:
            content = f.read()
            if 'POSTGRES_USER' not in content:
                log.error('No POSTGRES_USER found in .env file')
                log.info('You can edit it to match your criteria')
                log.info('You do not need to run this script to upgrade to 2.0.0')
                return False

            log.info('It looks like you are coming from a previous version of IRIS')
            if not silent:
                log.info('You can run this script to upgrade to 2.0.0')
            return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IRIS 2.0.0 upgrade script")
    parser.add_argument("-i", "--install", help="Install upgrade", action="store_true", required=False)
    parser.add_argument("-r", "--dry-run", help="Dry run upgrade and see changes", action="store_true",
                        required=False)
    parser.add_argument("-c", "--check", help="Check if upgrade looks doable",
                        action="store_true", required=False)

    args = parser.parse_args()
    iu = IrisUpgrade200()
    if args.install:
        iu.upgrade(args.dry_run)

    if args.check:
        iu.check()

