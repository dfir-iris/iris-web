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


FROM nginx:1.27

RUN apt-get update && apt-get install -y curl

# Used to pass protected files to the container through volumes
ARG NGINX_CONF_GID
ARG NGINX_CONF_FILE

RUN groupadd -g ${NGINX_CONF_GID} az-app-nginx-conf && usermod -a -G az-app-nginx-conf www-data

COPY entrypoint.sh /entrypoint.sh
RUN chmod 700 /entrypoint.sh
RUN chown www-data:www-data /entrypoint.sh

COPY ${NGINX_CONF_FILE} /etc/nginx/nginx.conf

# log
RUN touch /var/log/nginx/audit_platform_error.log && chown -R www-data:www-data /var/log/nginx/audit_platform_error.log
RUN touch /var/log/nginx/audit_platform_access.log && chown -R www-data:www-data /var/log/nginx/audit_platform_access.log

# Security
RUN touch /var/run/nginx.pid && chown -R www-data:www-data /var/run/nginx.pid /var/cache/nginx /etc/nginx/nginx.conf

RUN mkdir -p /www/certs/

USER www-data

HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail -k https://127.0.0.1:${INTERFACE_HTTPS_PORT:-443} || exit 1

ENTRYPOINT ["/entrypoint.sh"]