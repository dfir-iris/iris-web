from setuptools import setup

setup(
    name='iris-web',
    version='2.0.0b3',
    packages=['irisweb.app', 'irisweb.app.models', 'irisweb.app.schema', 'irisweb.app.datamgmt', 'irisweb.app.datamgmt.case', 'irisweb.app.datamgmt.client',
              'irisweb.app.datamgmt.manage', 'irisweb.app.datamgmt.context', 'irisweb.app.datamgmt.overview', 'irisweb.app.datamgmt.reporter',
              'irisweb.app.datamgmt.dashboard', 'irisweb.app.datamgmt.datastore', 'irisweb.app.datamgmt.activities', 'irisweb.app.datamgmt.exceptions',
              'irisweb.app.datamgmt.iris_engine', 'irisweb.app.blueprints', 'irisweb.app.blueprints.api', 'irisweb.app.blueprints.case',
              'irisweb.app.blueprints.login', 'irisweb.app.blueprints.manage', 'irisweb.app.blueprints.search', 'irisweb.app.blueprints.context',
              'irisweb.app.blueprints.profile', 'irisweb.app.blueprints.reports', 'irisweb.app.blueprints.overview', 'irisweb.app.blueprints.dashboard',
              'irisweb.app.blueprints.datastore', 'irisweb.app.blueprints.dim_tasks', 'irisweb.app.blueprints.activities',
              'irisweb.app.blueprints.demo_landing', 'irisweb.app.iris_engine', 'irisweb.app.iris_engine.utils', 'irisweb.app.iris_engine.backup',
              'irisweb.app.iris_engine.tasker', 'irisweb.app.iris_engine.updater', 'irisweb.app.iris_engine.reporter',
              'irisweb.app.iris_engine.access_control', 'irisweb.app.iris_engine.module_handler', 'irisweb.app.flask_dropzone', 'irisweb.tests',
              'irisweb.tests.unit', 'irisweb.tests.unit.datamgmt', 'irisweb.tests.unit.datamgmt.client', 'irisweb.tests.unit.blueprints',
              'irisweb.tests.unit.blueprints.case', 'irisweb.tests.unit.blueprints.manage', 'irisweb.tests.performance'],
    package_dir={'irisweb': '.'},
    url='https://github.com/dfir-iris/iris-web',
    license='LGPLv3',
    author='DFIR-IRIS',
    author_email='contact@dfir-iris',
    description='Setup file to build iris-web'
)
