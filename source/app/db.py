import collections
import json
from flask_sqlalchemy import SQLAlchemy
from functools import partial

SQLALCHEMY_ENGINE_OPTIONS = {
    "json_deserializer": partial(json.loads, object_pairs_hook=collections.OrderedDict),
    "pool_pre_ping": True
}

db = SQLAlchemy(engine_options=SQLALCHEMY_ENGINE_OPTIONS)  # flask-sqlalchemy