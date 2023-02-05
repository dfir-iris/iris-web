#!/usr/bin/env python3
#
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
    "POSTGRES_USER": "POSTGRES_ADMIN_USER",  # Need to stay up there
    "DB_USER": "POSTGRES_USER",
    "DB_PASS": "POSTGRES_PASSWORD",
    "DB_HOST": "POSTGRES_SERVER",
    "DB_PORT": "POSTGRES_PORT",
    "SECRET_KEY": "IRIS_SECRET_KEY",
    "SECURITY_PASSWORD_SALT": "IRIS_SECURITY_PASSWORD_SALT"
}


class IrisUpgrade200:

    def upgrade(self, dry_run=False):
        """
        Upgrade IRIS to 2.0.0
        """
        if not self.check():
            log.info('Upgrade aborted')
            return False

        content = None
        with open(root_dir / '.env', "r") as f:
            content = f.read()

            for old, new in env_upgrade_map.items():
                if f"{old}=" not in content:
                    continue

                if dry_run:
                    log.info(f'Dry run: would have replaced {old} with {new}')
                else:
                    log.info(f'Replacing {old} with {new}')
                    content = content.replace(f"{old}=", f"{new}=")

        if not dry_run:
            log.info('Writing new .env file')
            with open(root_dir / '.env', "w") as f:
                f.write(content)

            log.info('Upgrade done. Please check the changes. ')
            log.info('You can now start IRIS with docker-compose up -d')

    @staticmethod
    def check():
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
            log.info('You can run this script to upgrade to 2.0.0')
            return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IRIS 2.0.0 upgrade script")
    parser.add_argument("-i", "--install", help="Install upgrade", action="store_true", required=False)
    parser.add_argument("-d", "--dry-run", help="Dry run upgrade and see changes", action="store_true",
                        required=False)
    parser.add_argument("-c", "--check", help="Check if upgrade looks doable",
                        action="store_true", required=False)

    args = parser.parse_args()
    iu = IrisUpgrade200()
    if args.install:
        iu.upgrade(args.dry_run)

    if args.check:
        iu.check()

