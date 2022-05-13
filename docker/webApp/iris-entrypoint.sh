#!/bin/bash

#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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




target=${1-:app}

printf "Running ${target} ...\n"

if [[ "${target}" == iris-worker ]] ; then
    celery -A app.celery worker -E -B -l INFO &
else
    gunicorn app:app --worker-class eventlet --bind 0.0.0.0:8000 --timeout 180 --worker-connections 1000 --log-level=info &
fi

while true; do sleep 2; done

