
# Setup test environment
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Run tests

First activate the virtual environment:
```
source ./venv/bin/activate
```

Then start the development configuration of DFIR-IRIS server:
```
cp ../.env.tests.model ../.env
docker compose --file ../docker-compose.dev.yml up --detach --wait
```

Then run:
```
python -m unittest --verbose
```

To execute only one test, suffix with the fully qualified test name. Example:
```
python -m unittest tests_rest_assets.TestsRestAssets.test_create_asset_should_return_201
```

Tip: this is a way to spped up the develop/run test loop. To restart only the `app` docker, do:
```
docker compose stop app && docker compose --file ../docker-compose.dev.yml start app
```

Finally, stop the development server:
```
docker compose down
```

Tip: if you want to clear database data:
```
docker volume rm iris-web_db_data
```
