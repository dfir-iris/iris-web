# Iris Architecture

The IRIS coarse-grained architecture can be understood by looking at the docker-compose.yml file. The main elements are:

* db: postgresql database to store all application data
* app: backend application
* worker: most module hooks are processed by the worker 
* rabbitmq: message broker between the app and worker
* nginx: the front server to serve static files and dispatch requests to app

## Code organisation

This section explains how the code is organized within the major namespaces.
They reflect the layered architecture of the IRIS backend:

* blueprints
* business
* datamgmt

The IRIS backend is a Flask application.

### blueprints

This is the public API of the `app`. It contains all the endpoints: REST, GraphQL, Flask templates (pages and modals). 
The requests payloads are converted to business objects from `models` and passed down to calls into the business layer.

Enforcing the permissions, i.e. checking a user is allowed to perform an action, is done in this layer.

Forbidden imports in this layer:

* `from app.datamgmt`, as everything should go through the business layer first 
* `from sqlalchemy`

### business

This is where processing happens. The methods should exclusively manipulate business objects from the `models` namespace.

Forbidden imports in this layer:

* `from app import db`, as the business layer should not take case of persistence details but rather delegate to the
  `datamgmt` layer

### datamgmt

This layer handles persistence. It should be the only layer with knowledge of the database engine.

Forbidden imports in this layer:

* `from app.business`, as the business layer should call the persistence layer (not the other way around)

### models

The description of all objects handled by IRIS `business` layer and persisted through `datamgt`.

### alembic

This namespace takes care of the database migration. 
