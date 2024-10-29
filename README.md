
<p align="center">
    <img src="source/app/static/assets/img/logo.ico" />
</p>

<p align="center">
  Incident Response Investigation System
  <br>
  <i>Current Version v2.4.15</i>
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
It is divided in two main parts, IrisWeb and IrisModules.   
 - IrisWeb is the web application which contains the core of
Iris (web interface, database management, etc). 
 - IrisModules are extensions of the core that allow third parties to process
data via Iris (eg enrich IOCs with MISP and VT, upload and injection of EVTX into Splunk). 
 
IrisWeb can work without any modules though defaults ones are preinstalled. Head to ``Manage > Modules`` in the UI 
to configure and enable them. 

### Running Iris
To ease the installation and upgrades, Iris is shipped in Docker containers. Thanks to Docker compose, 
it can be ready in a few minutes.  

``` bash
#  Clone the iris-web repository
git clone https://github.com/dfir-iris/iris-web.git
cd iris-web

# Checkout to the last tagged version 
git checkout v2.4.15

# Copy the environment file 
cp .env.model .env

# Pull the dockers
docker compose pull

# Run IRIS 
docker compose up
```

Iris shall be available on the host interface, port 443, protocol HTTPS - ``https://<your_instance_ip>``.  
By default, an ``administrator`` account is created. The password is printed in stdout the very first time Iris is started. It won't be printed anymore after that.  
``WARNING :: post_init :: create_safe_admin :: >>>`` can be searched in the logs of the `webapp` docker to find the password.  
The initial password can be set via the [configuration](https://docs.dfir-iris.org/operations/configuration/).   

Iris is split on 5 Docker services, each with a different role.

- ``app``: The core, including web server, DB management, module management etc.
- ``db``: A PostgresSQL database
- ``RabbitMQ``: A RabbitMQ engine to handle jobs queuing and processing
- ``worker``: Jobs handler relying on RabbitMQ
- ``nginx``: A NGINX reverse proxy

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


