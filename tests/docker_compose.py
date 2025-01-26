#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

_DOCKER_COMPOSE = ['docker', 'compose']


class DockerCompose:

    def __init__(self, docker_compose_path, docker_compose_file):
        self._docker_compose_path = docker_compose_path
        self._docker_compose_file = docker_compose_file

    def start(self):
        subprocess.check_call(_DOCKER_COMPOSE + ['-f', self._docker_compose_file, 'up', '--detach'], cwd=self._docker_compose_path)

    def extract_all_logs(self):
        return subprocess.check_output(_DOCKER_COMPOSE + ['-f', self._docker_compose_file, 'logs', '--no-color'], cwd=self._docker_compose_path, universal_newlines=True)

    def stop(self):
        subprocess.check_call(_DOCKER_COMPOSE + ['-f', self._docker_compose_file, 'down', '--volumes'], cwd=self._docker_compose_path)
