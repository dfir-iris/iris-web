
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

Then run:
```
python -m unittest --verbose
```

To execute only one test, suffix with the fully qualified test name. Example:
```
python -m unittest tests.Tests.test_create_asset_should_not_fail
```
