#!/usr/bin/env python3
#
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
import gzip
from datetime import datetime
from app import app
import subprocess
from pathlib import Path

log = app.logger


def backup_iris_db():
    backup_file = Path(app.config.get('BACKUP_PATH')) / "database" / "backup-{}.sql.gz".format(
        datetime.now().strftime("%Y-%m-%d_%H%M%S"))

    completed_process = None
    with open(backup_file, 'w') as backup:
        completed_process = subprocess.run(
            ['/usr/local/bin/pg_dump', '-h', app.config.get('PG_SERVER'), '-p', app.config.get('PG_PORT'),
             '-U', app.config.get('PGA_ACCOUNT'),
             '--compress=9', '-c', '-O', '--if-exists', 'iris_db'],
            stdout=backup,
            env={'PGPASSWORD': app.config.get('PGA_PASSWD')})

    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        log.error(e)

    if backup_file.is_file():
        log.info(f'Backup completed in {backup_file}')

    return True