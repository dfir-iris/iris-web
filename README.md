
<p align="center">
  Incident Response Investigation System
  <br>
  <i>Current Version v3.0.0-beta.1</i>
  <br>
  <a href="https://v200.beta.dfir-iris.org">Online Demonstration</a>
</p>

# IRIS

[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](./LICENSE.txt)   
Iris is a web collaborative platform aiming to help incident responders sharing technical details during investigations. 

![demo_timeline](img/timeline_speed.gif)

## Table of contents
- [Getting Started](#getting-started)
  - [Run IrisWeb](#run-irisweb)
  - [Configuration](#configuration)
- [Versioning](#versioning)
- [Showcase](#showcase)
- [Documentation](#documentation)
  - [Upgrades](#upgrades)
  - [API](#api)
- [Help](#help)
- [Considerations](#considerations)
- [License](#license)


## Getting started

Starting with v3, IRIS ships as three coordinated repos:

- **iris-web** — this repo, the meta / umbrella. Owns the docker-compose stack, top-level docs, release orchestration.
- **[iris-backend](https://github.com/dfir-iris/iris-backend)** — Python/Flask API and workers.
- **[iris-frontend](https://github.com/dfir-iris/iris-frontend)** — SvelteKit UI.

The backend and frontend are wired into iris-web as git submodules. `docker compose up` pulls pre-built images from `ghcr.io/dfir-iris/iris-{backend,db,nginx,frontend}` — no build step, no submodule init required for pull-only deployments.

### Running Iris

``` bash
# Clone with submodules — only needed if you plan to build locally.
git clone --recursive https://github.com/dfir-iris/iris-web.git
cd iris-web

# Optional: pin to the last tagged version
git checkout v3.0.0-beta.1

# Copy and edit the environment template — set POSTGRES_PASSWORD,
# POSTGRES_ADMIN_PASSWORD, IRIS_SECRET_KEY, IRIS_SECURITY_PASSWORD_SALT,
# and IRIS_HOSTNAME at minimum.
cp .env.example .env

# Provide a TLS cert + key at certificates/web_certificates/iris_dev_cert.pem
# and iris_dev_key.pem (or set CERT_FILENAME/KEY_FILENAME in .env). For a
# quick self-signed pair:
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -keyout certificates/web_certificates/iris_dev_key.pem \
    -out certificates/web_certificates/iris_dev_cert.pem \
    -subj "/CN=iris.local" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

# Pull images from ghcr.io and start
docker compose up -d
```

IRIS is now available at ``https://<IRIS_HOSTNAME>`` (default: `https://localhost`, port 443).

By default, an ``administrator`` account is created. The password is printed to stdout the very first time IRIS starts.
``WARNING :: post_init :: create_safe_admin :: >>>`` can be searched in the logs of the `iris_app` container to find it, or you can pre-set it via `IRIS_ADM_PASSWORD` in `.env`.

The stack runs six services:

- ``app``: Flask API + web server (image: `iris-backend`)
- ``worker``: Celery jobs handler (image: `iris-backend`)
- ``db``: PostgreSQL (image: `iris-db`)
- ``rabbitmq``: broker for Celery
- ``nginx``: TLS termination + reverse proxy (image: `iris-nginx`)
- ``frontend``: SvelteKit SSR (image: `iris-frontend`)

### Building locally

To build images from the submodules instead of pulling:

``` bash
git submodule update --init --recursive
./scripts/dev-up.sh              # equivalent to `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`
```

### Configuration
There are three different options for configuring the settings and credentials: Azure Key Vault, Environment Variables and Configuration Files. This is also the order of priority, if a settings is not set it will fall back on the next option.
For all available configuration options see [configuration](https://docs.dfir-iris.org/operations/configuration/).

## Versioning
Starting from version 2.0.0, Iris is following the [Semantic Versioning 2.0](https://semver.org/) guidelines.   
The code ready for production is always tagged with a version number. 
``alpha`` and ``beta`` versions are **not** production-ready.  

Do not use the ``master`` branch in production. 

## Showcase
You can directly try Iris on our [demo instance](https://v200.beta.dfir-iris.org).  
One can also head to [tutorials](https://docs.dfir-iris.org/operations/tutorials/), we've put some videos there.  

## Documentation
A comprehensive documentation is available on [docs.dfir-iris.org](https://docs.dfir-iris.org).

### Upgrades
Please read the release notes when upgrading versions. Most of the time the migrations are handled automatically, but some
changes might require some manual labor depending on the version. 

### API
The API reference is available in the [documentation](https://docs.dfir-iris.org/operations/api/#references) or [documentation repository](https://github.com/dfir-iris/iris-doc-src).

## Help
You can reach us on [Discord](https://discord.gg/76tM6QUJza) or by [mail](mailto:contact@dfir-iris.org) if you have any question, issue or idea!   
We are also on [Twitter](https://twitter.com/dfir_iris) and [Matrix](https://matrix.to/#/#dfir-iris:matrix.org).  

## Considerations
Iris is still in its early stage. It can already be used in production, but please set backups of the database and DO NOT expose the interface on the Internet. We highly recommend using a private dedicated and secured network.

## License
The contents of this repository is available under [LGPL3 license](LICENSE.txt).

## Sponsoring
Special thanks to Deutsche Telekom Security GmbH for sponsoring us!


