#!/usr/bin/env bash

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

set -e

# envsubst will make a substitution on every $variable in a file, since the nginx file contains nginx variable like $host, we have to limit the substitution to this set
# otherwise, each nginx variable will be replaced by an empty string
envsubst '${INTERFACE_HTTPS_PORT} ${IRIS_UPSTREAM_SERVER} ${IRIS_UPSTREAM_PORT} ${SERVER_NAME} ${KEY_FILENAME} ${CERT_FILENAME}' < /etc/nginx/nginx.conf > /tmp/nginx.conf
cp /tmp/nginx.conf /etc/nginx/nginx.conf
rm /tmp/nginx.conf

exec nginx -g "daemon off;"
