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


#################
# COMPILE IMAGE #
#################
FROM python:3.9 AS compile-image
RUN apt-get update

RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

COPY source/dependencies /dependencies
COPY source/requirements.txt /

RUN pip3 install -r requirements.txt

###############
# BUILD IMAGE #
###############
FROM python:3.9 as iriswebapp
ENV PYTHONUNBUFFERED=1 DOCKERIZED=1

COPY --from=compile-image /opt/venv /opt/venv

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

# Define specific admin password at creation
#ENV IRIS_ADM_PASSWORD="MySuperFirstPasswordIWant"

RUN apt update
RUN apt install -y p7zip-full pgp rsync postgresql-client

RUN mkdir /iriswebapp/
RUN mkdir -p /home/iris/certificates/{rootCA,web_certificates}
RUN mkdir -p /home/iris/user_templates
RUN mkdir -p /home/iris/server_data
RUN mkdir -p /home/iris/server_data/backup
RUN mkdir -p /home/iris/server_data/updates
RUN mkdir -p /home/iris/server_data/custom_assets
RUN mkdir -p /home/iris/server_data/datastore

WORKDIR /iriswebapp

COPY docker/webApp/iris-entrypoint.sh .
COPY docker/webApp/wait-for-iriswebapp.sh .
COPY ./source .

# Add execution right to binaries needed by evtx2splunk for iris_evtx module
RUN chmod +x /iriswebapp/dependencies/evtxdump_binaries/linux/x64/fd
RUN chmod +x /iriswebapp/dependencies/evtxdump_binaries/linux/x64/evtx_dump

RUN chmod +x iris-entrypoint.sh
RUN chmod +x wait-for-iriswebapp.sh
#ENTRYPOINT [ "./iris-entrypoint.sh" ]
