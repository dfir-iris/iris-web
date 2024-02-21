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
import subprocess
from datetime import datetime
from pathlib import Path

from app import app

log = app.logger


def backup_iris_db():
    logs = []
    backup_dir = Path(app.config.get('BACKUP_PATH')) / "database"

    try:

        if not backup_dir.is_dir():
            backup_dir.mkdir()

    except Exception as e:
        logs.append('Unable to create backup directory')
        logs.append(str(e))
        return True, logs

    backup_file = Path(app.config.get('BACKUP_PATH')) / "database" / "backup-{}.sql.gz".format(
        datetime.now().strftime("%Y-%m-%d_%H%M%S"))

    try:
        logs.append(f'Saving database')
        with open(backup_file, 'w') as backup:
            completed_process = subprocess.run(
                [f'{app.config.get("PG_CLIENT_PATH")}/pg_dump', '-h',
                 app.config.get('PG_SERVER'), '-p',
                 app.config.get('PG_PORT'),
                 '-U', app.config.get('PGA_ACCOUNT'),
                 '--compress=9', '-c', '-O', '--if-exists', app.config.get('PG_DB')],
                stdout=backup,
                env={'PGPASSWORD': app.config.get('PGA_PASSWD')},
                check=True
            )

    except Exception as e:
        logs.append('Something went wrong backing up DB')
        logs.append(str(e))
        return True, logs

    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        logs.append('Something went wrong backing up DB')
        logs.append(str(e))
        return True, logs

    if backup_file.is_file() and backup_file.stat().st_size != 0:
        logs.append(f'Backup completed in {backup_file}')

    return False, logs
