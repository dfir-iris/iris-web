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


FROM postgres:12-alpine

RUN apk add --update --no-cache clang clang-dev llvm
RUN apk add --update --no-cache clang-extra-tools

RUN apk add --update --no-cache git build-base \
 && git clone https://github.com/eulerto/pg_similarity.git \
 && cd pg_similarity \
 && USE_PGXS=1 make \
 && USE_PGXS=1 make install \
 && apk del git build-base \
 && rm -rf /var/cache/apk/*

COPY create_user.sh   /docker-entrypoint-initdb.d/10-create_user.sh