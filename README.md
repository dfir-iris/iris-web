
<p align="center">
    <img src="source/app/static/assets/img/logo.ico" />
</p>

<p align="center">
  Incident Response Investigation System
  <br>
  <br>
</p>

# IRIS

[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](./LICENSE.txt)   
IRIS is a web collaborative platform for incident response analysts allowing to share investigations at a technical level. 

## Getting started
It is divided in two main parts, IrisWeb and IrisModules.   
 - IrisWeb is the web application which contains the core of
Iris (web interface, database management, etc). 
 - IrisModules are extensions of the core that allow third parties to process
data via Iris (eg upload and injection of EVTX into Splunk). 
 
IrisWeb can work without any modules and by default none are enabled.  

A first module called [IrisEVTXModule](https://github.com/dfir-iris/iris-evtx-module) is provided and installed in 
IRIS's Python environment when using the docker-compose building process. 
In order to be added to IRIS and configured, see the [documentation](https://dfir-iris.github.io).

### Run IrisWeb 
The app has 5 dockers: 
- `app - iriswebapp_app`: The core of IrisWeb 
- `db`: The Postgres database 
- `rabbitmq`: It's in the name 
- `worker`: Jobs handler relying on RabbitMq 
- `nginx`: The reverse proxy

The NGINX service uses the certificate pair specified in .env. A pair is provided 
in the `./docker/dev_certs` repository, but you might want to change with your own certificate.
Below is an example command to generate such self-signed certificates:
``` 
openssl req -new -newkey rsa:2048 -sha256 -days 365 -nodes -x509 -keyout certificate.key -out certificate.crt
```

**To run:**
1. Clone the repo and cd into it
2. Copy `.env.model` into `.env`
3. (Optional if you just want to try) If used in production, please configure the .env file at 
the root of the project:
   1. Nginx: you might want to specify your own certificate as specified above
   2. Database credentials: **POSTGRES_PASSWORD** and **DB_PASS** (you can also customise the usernames)
   3. IRIS secrets: **SECRET_KEY** and **SECURITY_PASSWORD_SALT**
4. Build `docker-compose build`
5. Run `docker-compose up` 

A first account called **administrator** is created by default, the password is randomly 
created and **output in the docker `app` service**. If you want to define an admin password
at the first start, you can also create and define the environment variable **IRIS_ADM_PASSWORD**
in the `app` docker instance (see [webApp Dockerfile](./docker/webApp/Dockerfile)).

Once it is up, go to https://<your_instance>:4433, login as administrator, and start using IRIS!
We also recommend immediately changing your administrator's password, either on its profile page or in the *Users* management page.

# Documentation

A more comprehensive documentation is available on [dfir-iris.github.io](https://dfir-iris.github.io), or one can build 
the documentation available in [here](https://github.com/dfir-iris/iris-doc-src).

## API

The API reference is available in the [documentation](https://dfir-iris.github.io) or [documentation repository](https://github.com/dfir-iris/iris-doc-src).

## Help 

You can reach us on [Discord](https://discord.gg/fwuXkpBHGz) if you have any question, issue or idea !

## License

The contents of this repository is available under [LGPL3 license](LICENSE.txt).

