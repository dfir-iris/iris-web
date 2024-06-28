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
import json

from pathlib import Path

import glob
import os
import random
import secrets
import string
import socket
import time
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, exc, or_, text
from sqlalchemy_utils import create_database
from sqlalchemy_utils import database_exists

from app import app
from app import bc
from app import celery
from app import db
from app.datamgmt.iris_engine.modules_db import iris_module_disable_by_id
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_organisation
from app.iris_engine.access_control.utils import ac_add_user_effective_access
from app.iris_engine.demo_builder import create_demo_cases
from app.iris_engine.access_control.utils import ac_get_mask_analyst
from app.datamgmt.manage.manage_groups_db import get_group_by_name
from app.iris_engine.access_control.utils import ac_get_mask_full_permissions
from app.iris_engine.module_handler.module_handler import check_module_health
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.iris_engine.module_handler.module_handler import register_module
from app.models import create_safe_limited
from app.models.alerts import Severity, AlertStatus, AlertResolutionStatus
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.cases import Cases, CaseState
from app.models.cases import Client
from app.models.models import AnalysisStatus, CaseClassification, ReviewStatus, ReviewStatusList, EvidenceTypes
from app.models.models import AssetsType
from app.models.models import EventCategory
from app.models.models import IocType
from app.models.models import IrisHook
from app.models.models import IrisModule
from app.models.models import Languages
from app.models.models import OsType
from app.models.models import ReportType
from app.models.models import ServerSettings
from app.models.models import TaskStatus
from app.models.models import Tlp
from app.models.models import create_safe
from app.models.models import create_safe_attr
from app.models.models import get_by_value_or_create
from app.models.models import get_or_create
from app.iris_engine.demo_builder import create_demo_users

log = app.logger

# Get the database host and port from environment variables
db_host = app.config.get('PG_SERVER')
db_port = int(app.config.get('PG_PORT'))

# Get the retry parameters from environment variables
retry_count = int(app.config.get('DB_RETRY_COUNT'))
retry_delay = int(app.config.get('DB_RETRY_DELAY'))


def connect_to_database(host: str, port: int) -> bool:
    """Attempts to connect to a database at the specified host and port.

    Args:
        host: A string representing the hostname or IP address of the database server.
        port: An integer representing the port number to connect to.

    Returns:
        A boolean value indicating whether the connection was successful.
    """
    # Create a new socket object
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Try to connect to the database
        s.connect((host, port))
        # If the connection was successful, close the socket and return True
        s.close()
        return True
    except socket.error:
        # If the connection failed, close the socket and return False
        s.close()
        return False


def run_post_init(development=False):
    """Runs post-initiation steps for the IRIS application.

    Args:
        development: A boolean value indicating whether the application is running in development mode.
    """
    # Log the IRIS version and post-initiation steps
    log.info(f'IRIS {app.config.get("IRIS_VERSION")}')
    log.info("Running post initiation steps")

    if os.getenv("IRIS_WORKER") is None:
        create_directories()

        # Attempt to connect to the database with retries
        log.info("Attempting to connect to the database...")
        for i in range(retry_count):
            log.info("Connecting to database, attempt " + str(i+1) + "/" + str(retry_count))
            conn = connect_to_database(db_host, db_port)
            if conn:
                break
            log.info("Retrying in " + str(retry_delay) + "seconds...")
            time.sleep(retry_delay)
        # If the connection is still not established, exit the script
        if not conn:
            log.info("Failed to connect to database after " + str(retry_count) + " attempts.")
            exit(1)

        # Setup database before everything
        #log.info("Adding pgcrypto extension")
        #pg_add_pgcrypto_ext()

        # Setup database before everything
        with app.app_context():
            log.info("Creating all Iris tables")
            db.create_all(bind_key=None)
            db.session.commit()

            log.info("Creating Celery metatasks tables")
            create_safe_db(db_name="iris_tasks")
            db.create_all(bind_key="iris_tasks")
            db.session.commit()

            log.info("Running DB migration")

            alembic_cfg = Config(file_='app/alembic.ini')
            alembic_cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
            command.upgrade(alembic_cfg, 'head')

            # Create base server settings if they don't exist
            srv_settings = ServerSettings.query.first()
            if srv_settings is None:
                log.info("Creating base server settings")
                create_safe_server_settings()
                srv_settings = ServerSettings.query.first()

            prevent_objects = srv_settings.prevent_post_objects_repush

            # Create base languages, OS types, IOC types, attributes, report types, TLP, event categories, assets,
            # analysis status, case classification, task status, severities, alert status, case states, and hooks
            log.info("Creating base languages")
            create_safe_languages()

            log.info("Creating base os types")
            create_safe_os_types()

            if not prevent_objects:
                log.info("Creating base IOC types")
                create_safe_ioctypes()

            log.info("Creating base attributes")
            create_safe_attributes()

            log.info("Creating base report types")
            create_safe_report_types()

            log.info("Creating base TLP")
            create_safe_tlp()

            log.info("Creating base events categories")
            create_safe_events_cats()

            if not prevent_objects:
                log.info("Creating base assets")
                create_safe_assets()

            log.info("Creating base analysis status")
            create_safe_analysis_status()

            if not prevent_objects:
                log.info("Creating base case classification")
                create_safe_classifications()

            log.info("Creating base tasks status")
            create_safe_task_status()

            log.info("Creating base severities")
            create_safe_severities()

            log.info("Creating base alert status")
            create_safe_alert_status()

            log.info("Creating base evidence types")
            create_safe_evidence_types()

            log.info("Creating base alert resolution status")
            create_safe_alert_resolution_status()

            if not prevent_objects:
                log.info("Creating base case states")
                create_safe_case_states()

            log.info("Creating base review status")
            create_safe_review_status()

            log.info("Creating base hooks")
            create_safe_hooks()

            # Create initial authorization model, administrative user, and customer
            log.info("Creating initial authorisation model")
            def_org, gadm, ganalysts = create_safe_auth_model()

            log.info("Creating first administrative user")
            admin, pwd = create_safe_admin(def_org=def_org, gadm=gadm)

            if not srv_settings.prevent_post_mod_repush:
                log.info("Registering default modules")
                register_default_modules()

            log.info("Creating initial customer")
            client = create_safe_client()

            log.info("Creating initial case")
            create_safe_case(
                user=admin,
                client=client,
                groups=[gadm, ganalysts]
            )

            # Setup symlinks for custom_assets
            log.info("Creating symlinks for custom asset icons")
            custom_assets_symlinks()

            # If demo mode is enabled, create demo users and cases
            if app.config.get('DEMO_MODE_ENABLED') == 'True':
                log.warning("============================")
                log.warning("|  THIS IS DEMO INSTANCE   |")
                log.warning("| DO NOT USE IN PRODUCTION |")
                log.warning("============================")
                users_data = create_demo_users(def_org, gadm, ganalysts,
                                               int(app.config.get('DEMO_USERS_COUNT', 10)),
                                               app.config.get('DEMO_USERS_SEED'),
                                               int(app.config.get('DEMO_ADM_COUNT', 4)),
                                               app.config.get('DEMO_ADM_SEED'))

                create_demo_cases(users_data=users_data,
                                  cases_count=int(app.config.get('DEMO_CASES_COUNT', 20)),
                                  clients_count=int(app.config.get('DEMO_CLIENTS_COUNT', 4)))

            # Log completion message
            log.info("Post-init steps completed")
            log.warning("===============================")
            log.warning(f"| IRIS IS READY on port  {os.getenv('INTERFACE_HTTPS_PORT')} |")
            log.warning("===============================")

            # If an administrative user was created, log their credentials
            if pwd is not None:
                log.info(f'You can now login with user {admin.user} and password >>> {pwd} <<< '
                         f'on {os.getenv("INTERFACE_HTTPS_PORT")}')


def create_safe_db(db_name):
    """Creates a new database with the specified name if it does not already exist.

    Args:
        db_name: A string representing the name of the database to create.
    """
    # Create a new engine object for the specified database
    engine = create_engine(app.config["SQALCHEMY_PIGGER_URI"] + db_name)

    # Check if the database already exists
    if not database_exists(engine.url):
        # If the database does not exist, create it
        create_database(engine.url)

    # Dispose of the engine object
    engine.dispose()


def create_safe_hooks():
    # --- Alert
    create_safe(db.session, IrisHook, hook_name='on_postload_alert_create',
                hook_description='Triggered on alert creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_delete',
                hook_description='Triggered on alert deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_update',
                hook_description='Triggered on alert update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_resolution_update',
                hook_description='Triggered on alert resolution update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_status_update',
                hook_description='Triggered on alert status update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_escalate',
                hook_description='Triggered on alert escalation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_merge',
                hook_description='Triggered on alert merge, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_unmerge',
                hook_description='Triggered on alert unmerge, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_alert',
                hook_description='Triggered upon user action')

    # --- Case
    create_safe(db.session, IrisHook, hook_name='on_preload_case_create',
                hook_description='Triggered on case creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_case_create',
                hook_description='Triggered on case creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_case_delete',
                hook_description='Triggered on case deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_case_delete',
                hook_description='Triggered on case deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_case_update',
                hook_description='Triggered on case update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_case',
                hook_description='Triggered upon user action')

    # --- Assets
    create_safe(db.session, IrisHook, hook_name='on_preload_asset_create',
                hook_description='Triggered on asset creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_create',
                hook_description='Triggered on asset creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_asset_update',
                hook_description='Triggered on asset update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_update',
                hook_description='Triggered on asset update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_asset_delete',
                hook_description='Triggered on asset deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_delete',
                hook_description='Triggered on asset deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_asset',
                hook_description='Triggered upon user action')

    # --- Notes
    create_safe(db.session, IrisHook, hook_name='on_preload_note_create',
                hook_description='Triggered on note creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_note_create',
                hook_description='Triggered on note creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_note_update',
                hook_description='Triggered on note update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_note_update',
                hook_description='Triggered on note update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_note_delete',
                hook_description='Triggered on note deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_note_delete',
                hook_description='Triggered on note deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_note',
                hook_description='Triggered upon user action')

    # --- iocs
    create_safe(db.session, IrisHook, hook_name='on_preload_ioc_create',
                hook_description='Triggered on ioc creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_create',
                hook_description='Triggered on ioc creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_ioc_update',
                hook_description='Triggered on ioc update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_update',
                hook_description='Triggered on ioc update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_ioc_delete',
                hook_description='Triggered on ioc deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_delete',
                hook_description='Triggered on ioc deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_ioc',
                hook_description='Triggered upon user action')

    # --- events
    create_safe(db.session, IrisHook, hook_name='on_preload_event_create',
                hook_description='Triggered on event creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_event_create',
                hook_description='Triggered on event creation, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_preload_event_duplicate',
                hook_description='Triggered on event duplication, before commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_event_update',
                hook_description='Triggered on event update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_event_update',
                hook_description='Triggered on event update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_event_delete',
                hook_description='Triggered on event deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_event_delete',
                hook_description='Triggered on event deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_event',
                hook_description='Triggered upon user action')

    # --- evidence
    create_safe(db.session, IrisHook, hook_name='on_preload_evidence_create',
                hook_description='Triggered on evidence creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_create',
                hook_description='Triggered on evidence creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_evidence_update',
                hook_description='Triggered on evidence update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_update',
                hook_description='Triggered on evidence update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_evidence_delete',
                hook_description='Triggered on evidence deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_delete',
                hook_description='Triggered on evidence deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_evidence',
                hook_description='Triggered upon user action')

    # --- tasks
    create_safe(db.session, IrisHook, hook_name='on_preload_task_create',
                hook_description='Triggered on task creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_task_create',
                hook_description='Triggered on task creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_task_update',
                hook_description='Triggered on task update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_task_update',
                hook_description='Triggered on task update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_task_delete',
                hook_description='Triggered on task deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_task_delete',
                hook_description='Triggered on task deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_task',
                hook_description='Triggered upon user action')

    # --- global tasks
    create_safe(db.session, IrisHook, hook_name='on_preload_global_task_create',
                hook_description='Triggered on global task creation, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_global_task_create',
                hook_description='Triggered on global task creation, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_global_task_update',
                hook_description='Triggered on task update, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_global_task_update',
                hook_description='Triggered on global task update, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_preload_global_task_delete',
                hook_description='Triggered on task deletion, before commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_global_task_delete',
                hook_description='Triggered on global task deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_manual_trigger_global_task',
                hook_description='Triggered upon user action')

    # --- reports
    create_safe(db.session, IrisHook, hook_name='on_preload_report_create',
                hook_description='Triggered on report creation, before generation in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_report_create',
                hook_description='Triggered on report creation, before download of the document')

    create_safe(db.session, IrisHook, hook_name='on_preload_activities_report_create',
                hook_description='Triggered on activities report creation, before generation in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_activities_report_create',
                hook_description='Triggered on activities report creation, before download of the document')

    # --- comments
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_commented',
                hook_description='Triggered on event commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_comment_update',
                hook_description='Triggered on event comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_asset_comment_delete',
                hook_description='Triggered on event comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_commented',
                hook_description='Triggered on evidence commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_comment_update',
                hook_description='Triggered on evidence comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_evidence_comment_delete',
                hook_description='Triggered on evidence comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_task_commented',
                hook_description='Triggered on task commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_task_comment_update',
                hook_description='Triggered on task comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_task_comment_delete',
                hook_description='Triggered on task comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_commented',
                hook_description='Triggered on IOC commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_comment_update',
                hook_description='Triggered on IOC comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_ioc_comment_delete',
                hook_description='Triggered on IOC comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_event_commented',
                hook_description='Triggered on event commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_event_comment_update',
                hook_description='Triggered on event comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_event_comment_delete',
                hook_description='Triggered on event comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_note_commented',
                hook_description='Triggered on note commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_note_comment_update',
                hook_description='Triggered on note comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_note_comment_delete',
                hook_description='Triggered on note comment deletion, after commit in DB')

    create_safe(db.session, IrisHook, hook_name='on_postload_alert_commented',
                hook_description='Triggered on alert commented, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_alert_comment_update',
                hook_description='Triggered on alert comment update, after commit in DB')
    create_safe(db.session, IrisHook, hook_name='on_postload_alert_comment_delete',
                hook_description='Triggered on alert comment deletion, after commit in DB')


def pg_add_pgcrypto_ext():
    """Adds the pgcrypto extension to the PostgreSQL database.

    This extension provides cryptographic functions for PostgreSQL.

    """

    # Set the application context
    with app.app_context():

        # Open a connection to the iris_db database
        with db.engine.connect() as con:
            # Execute a SQL command to create the pgcrypto extension if it does not already exist
            con.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto CASCADE;'))
            db.session.commit()
            log.info("pgcrypto extension added")


def create_safe_languages():
    """Creates new Language objects if they do not already exist.

    This function creates new Language objects with the specified name and code
    if they do not already exist in the database.

    """
    # Create new Language objects for each language
    create_safe(db.session, Languages, name="french", code="FR")
    create_safe(db.session, Languages, name="english", code="EN")
    create_safe(db.session, Languages, name="german", code="DE")
    create_safe(db.session, Languages, name="bulgarian", code="BG")
    create_safe(db.session, Languages, name="croatian", code="HR")
    create_safe(db.session, Languages, name="danish", code="DK")
    create_safe(db.session, Languages, name="dutch", code="NL")
    create_safe(db.session, Languages, name="estonian", code="EE")
    create_safe(db.session, Languages, name="finnish", code="FI")
    create_safe(db.session, Languages, name="greek", code="GR")
    create_safe(db.session, Languages, name="hungarian", code="HU")
    create_safe(db.session, Languages, name="irish", code="IE")
    create_safe(db.session, Languages, name="italian", code="IT")
    create_safe(db.session, Languages, name="latvian", code="LV")
    create_safe(db.session, Languages, name="lithuanian", code="LT")
    create_safe(db.session, Languages, name="maltese", code="MT")
    create_safe(db.session, Languages, name="polish", code="PL")
    create_safe(db.session, Languages, name="portuguese", code="PT")
    create_safe(db.session, Languages, name="romanian", code="RO")
    create_safe(db.session, Languages, name="slovak", code="SK")
    create_safe(db.session, Languages, name="slovenian", code="SI")
    create_safe(db.session, Languages, name="spanish", code="ES")
    create_safe(db.session, Languages, name="swedish", code="SE")
    create_safe(db.session, Languages, name="indian", code="IN")
    create_safe(db.session, Languages, name="chinese", code="CN")
    create_safe(db.session, Languages, name="korean", code="KR")
    create_safe(db.session, Languages, name="arabic", code="AR")
    create_safe(db.session, Languages, name="japanese", code="JP")
    create_safe(db.session, Languages, name="turkish", code="TR")
    create_safe(db.session, Languages, name="vietnamese", code="VN")
    create_safe(db.session, Languages, name="thai", code="TH")
    create_safe(db.session, Languages, name="hebrew", code="IL")
    create_safe(db.session, Languages, name="czech", code="CZ")
    create_safe(db.session, Languages, name="norwegian", code="NO")
    create_safe(db.session, Languages, name="brazilian", code="BR")
    create_safe(db.session, Languages, name="ukrainian", code="UA")
    create_safe(db.session, Languages, name="catalan", code="CA")
    create_safe(db.session, Languages, name="serbian", code="RS")
    create_safe(db.session, Languages, name="persian", code="IR")
    create_safe(db.session, Languages, name="afrikaans", code="ZA")
    create_safe(db.session, Languages, name="albanian", code="AL")
    create_safe(db.session, Languages, name="armenian", code="AM")


def create_safe_events_cats():
    """Creates new EventCategory objects if they do not already exist.

    This function creates new EventCategory objects with the specified name
    if they do not already exist in the database.

    """
    # Create new EventCategory objects for each category
    create_safe(db.session, EventCategory, name="Unspecified")
    create_safe(db.session, EventCategory, name="Legitimate")
    create_safe(db.session, EventCategory, name="Remediation")
    create_safe(db.session, EventCategory, name="Initial Access")
    create_safe(db.session, EventCategory, name="Execution")
    create_safe(db.session, EventCategory, name="Persistence")
    create_safe(db.session, EventCategory, name="Privilege Escalation")
    create_safe(db.session, EventCategory, name="Defense Evasion")
    create_safe(db.session, EventCategory, name="Credential Access")
    create_safe(db.session, EventCategory, name="Discovery")
    create_safe(db.session, EventCategory, name="Lateral Movement")
    create_safe(db.session, EventCategory, name="Collection")
    create_safe(db.session, EventCategory, name="Command and Control")
    create_safe(db.session, EventCategory, name="Exfiltration")
    create_safe(db.session, EventCategory, name="Impact")


def create_safe_classifications():
    """Creates new CaseClassification objects if they do not already exist.

    This function reads the MISP classification taxonomy from a JSON file and creates
    new CaseClassification objects with the specified name, name_expanded, and description
    if they do not already exist in the database.

    """
    # Read the MISP classification taxonomy from a JSON file
    log.info("Reading MISP classification taxonomy from resources/misp.classification.taxonomy.json")
    with open(Path(__file__).parent / 'resources' / 'misp.classification.taxonomy.json') as data_file:
        data = json.load(data_file)
        # Iterate over each classification in the taxonomy
        for c in data.get('values'):
            predicate = c.get('predicate')
            entries = c.get('entry')
            # Iterate over each entry in the classification
            for entry in entries:
                # Create a new CaseClassification object with the specified name, name_expanded, and description
                create_safe(db.session, CaseClassification,
                            name=f"{predicate}:{entry.get('value')}",
                            name_expanded=f"{predicate.title()}: {entry.get('expanded')}",
                            description=entry['description'])


def create_safe_analysis_status():
    """Creates new AnalysisStatus objects if they do not already exist.

    This function creates new AnalysisStatus objects with the specified name
    if they do not already exist in the database.

    """
    # Create new AnalysisStatus objects for each status
    create_safe(db.session, AnalysisStatus, name='Unspecified')
    create_safe(db.session, AnalysisStatus, name='To be done')
    create_safe(db.session, AnalysisStatus, name='Started')
    create_safe(db.session, AnalysisStatus, name='Pending')
    create_safe(db.session, AnalysisStatus, name='Canceled')
    create_safe(db.session, AnalysisStatus, name='Done')


def create_safe_task_status():
    """Creates new TaskStatus objects if they do not already exist.

    This function creates new TaskStatus objects with the specified status name,
    status description, and Bootstrap color if they do not already exist in the database.

    """
    # Create new TaskStatus objects for each status
    create_safe(db.session, TaskStatus, status_name='To do', status_description="", status_bscolor="danger")
    create_safe(db.session, TaskStatus, status_name='In progress', status_description="", status_bscolor="warning")
    create_safe(db.session, TaskStatus, status_name='On hold', status_description="", status_bscolor="muted")
    create_safe(db.session, TaskStatus, status_name='Done', status_description="", status_bscolor="success")
    create_safe(db.session, TaskStatus, status_name='Canceled', status_description="", status_bscolor="muted")


def create_safe_severities():
    """Creates new Severity objects if they do not already exist.

    This function creates new Severity objects with the specified severity name
    and severity description if they do not already exist in the database.

    """
    # Create new Severity objects for each severity level
    create_safe(db.session, Severity, severity_name='Unspecified', severity_description="Unspecified")
    create_safe(db.session, Severity, severity_name='Informational', severity_description="Informational")
    create_safe(db.session, Severity, severity_name='Low', severity_description="Low")
    create_safe(db.session, Severity, severity_name='Medium', severity_description="Medium")
    create_safe(db.session, Severity, severity_name='High', severity_description="High")
    create_safe(db.session, Severity, severity_name='Critical', severity_description="Critical")


def create_safe_alert_status():
    """Creates new AlertStatus objects if they do not already exist.

    This function creates new AlertStatus objects with the specified status name
    and status description if they do not already exist in the database.

    """
    # Create new AlertStatus objects for each status
    create_safe(db.session, AlertStatus, status_name='Unspecified', status_description="Unspecified")
    create_safe(db.session, AlertStatus, status_name='New', status_description="Alert is new and unassigned")
    create_safe(db.session, AlertStatus, status_name='Assigned', status_description="Alert is assigned to a user and "
                                                                                    "pending investigation")
    create_safe(db.session, AlertStatus, status_name='In progress', status_description="Alert is being investigated")
    create_safe(db.session, AlertStatus, status_name='Pending', status_description="Alert is in a pending state")
    create_safe(db.session, AlertStatus, status_name='Closed', status_description="Alert closed, no action taken")
    create_safe(db.session, AlertStatus, status_name='Merged', status_description="Alert merged into an existing case")
    create_safe(db.session, AlertStatus, status_name='Escalated', status_description="Alert converted to a new case")


def create_safe_evidence_types():
    """Creates new Evidence Types objects if they do not already exist.

    This function creates new Evidence Types objects with the specified type name
    and type description if they do not already exist in the database.

    """
    # Create new EvidenceType objects for each status
    create_safe(db.session, EvidenceTypes, name='Unspecified', description="Unspecified")

    create_safe(db.session, EvidenceTypes, name='HDD image - Generic', description="Generic copy of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - DD - Other', description="DD copy of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - DD - Windows', description="DD copy of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - DD - Unix', description="DD copy of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - DD - MacOS', description="DD copy of an hard drive")

    create_safe(db.session, EvidenceTypes, name='HDD image - E01 - Other', description="E01 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - E01 - Windows', description="E01 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - E01 - Unix', description="E01 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - E01 - MacOS', description="E01 acquisition of an hard drive")

    create_safe(db.session, EvidenceTypes, name='HDD image - AFF4 - Other', description="AFF4 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - AFF4 - Windows', description="AFF4 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - AFF4 - Unix', description="AFF4 acquisition of an hard drive")
    create_safe(db.session, EvidenceTypes, name='HDD image - AFF4 - MacOS', description="AFF4 acquisition of an hard drive")

    create_safe(db.session, EvidenceTypes, name='SSD image - Generic', description="Generic copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - DD - Other', description="DD copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - DD - Windows', description="DD copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - DD - Unix', description="DD copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - DD - MacOS', description="DD copy of an solid state drive")

    create_safe(db.session, EvidenceTypes, name='SSD image - E01 - Other', description="EO1 copy of a solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - E01 - Windows', description="EO1 copy of a solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - E01 - Unix', description="EO1 copy of a solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - E01 - MacOS', description="EO1 copy of MacOS on a solid state drive")

    create_safe(db.session, EvidenceTypes, name='SSD image - AFF4 - Other', description="AFF4 copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - AFF4 - Windows', description="AFF4 copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - AFF4 - Unix', description="AFF4 copy of an solid state drive")
    create_safe(db.session, EvidenceTypes, name='SSD image - AFF4 - MacOS', description="AFF4 copy of an solid state drive")

    create_safe(db.session, EvidenceTypes, name='VM image - Generic', description="Generic copy of a VM ")
    create_safe(db.session, EvidenceTypes, name='VM image - Linux Server', description="Copy of a Linux Server VM")
    create_safe(db.session, EvidenceTypes, name='VM image - Windows Server', description="Copy of a Windows Server VM")
    create_safe(db.session, EvidenceTypes, name='VM image - Windows Server', description="Copy of a Windows Server VM")

    create_safe(db.session, EvidenceTypes, name='Phone Image - Android', description="Copy of an Android phone")
    create_safe(db.session, EvidenceTypes, name='Phone Image - iPhone', description="Copy of an iPhone")
    create_safe(db.session, EvidenceTypes, name='Phone backup - Android (adb)', description="adb backup of an Android")
    create_safe(db.session, EvidenceTypes, name='Phone backup - iPhone (iTunes)', description="iTunes backup of an iPhone")

    create_safe(db.session, EvidenceTypes, name='Tablet Image - Android', description="Copy of an Android tablet")
    create_safe(db.session, EvidenceTypes, name='Tablet Image - iPad', description="Copy of an iPad tablet")
    create_safe(db.session, EvidenceTypes, name='Tablet backup - Android (adb)', description="adb backup of an Android tablet")
    create_safe(db.session, EvidenceTypes, name='Tablet backup - iPad (iTunes)', description="iTunes backup of an iPad")

    create_safe(db.session, EvidenceTypes, name='Collection - Velociraptor', description="Velociraptor collection")
    create_safe(db.session, EvidenceTypes, name='Collection - ORC', description="ORC collection")
    create_safe(db.session, EvidenceTypes, name='Collection - KAPE', description="KAPE collection")

    create_safe(db.session, EvidenceTypes, name="Memory acquisition - Physical RAM", description="Physical RAM acquisition")
    create_safe(db.session, EvidenceTypes, name="Memory acquisition - VMEM", description="vmem file")

    create_safe(db.session, EvidenceTypes, name="Logs - Linux", description="Standard Linux logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Windows EVTX", description="Standard Windows EVTX logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Windows EVT", description="Standard Windows EVT logs")
    create_safe(db.session, EvidenceTypes, name="Logs - MacOS", description="Standard MacOS logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Generic", description="Generic logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Firewall", description="Firewall logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Proxy", description="Proxy logs")
    create_safe(db.session, EvidenceTypes, name="Logs - DNS", description="DNS logs")
    create_safe(db.session, EvidenceTypes, name="Logs - Email", description="Email logs")

    create_safe(db.session, EvidenceTypes, name="Executable - Windows (PE)", description="Generic Windows executable")
    create_safe(db.session, EvidenceTypes, name="Executable - Linux (ELF)", description="Generic Linux executable")
    create_safe(db.session, EvidenceTypes, name="Executable - MacOS (Mach-O)", description="Generic MacOS executable")
    create_safe(db.session, EvidenceTypes, name="Executable - Generic", description="Generic executable")

    create_safe(db.session, EvidenceTypes, name="Script - Generic", description="Generic script")

    create_safe(db.session, EvidenceTypes, name="Generic - Data blob", description="Generic blob of data")


def create_safe_alert_resolution_status():
    """Creates new AlertResolutionStatus objects if they do not already exist.

    This function creates new AlertResolutionStatus objects with the specified resolution_status_name
    and resolution_status_description if they do not already exist in the database.

    """
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='False Positive',
                resolution_status_description="The alert was a false positive")
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='True Positive With Impact',
                resolution_status_description="The alert was a true positive and had an impact")
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='True Positive Without Impact',
                resolution_status_description="The alert was a true positive but had no impact")
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='Not Applicable',
                resolution_status_description="The alert is not applicable")
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='Unknown',
                resolution_status_description="Unknown resolution status")
    create_safe(db.session, AlertResolutionStatus, resolution_status_name='Legitimate',
                resolution_status_description="The alert is acceptable and expected")


def create_safe_case_states():
    """Creates new CaseState objects if they do not already exist.

    This function creates new CaseState objects with the specified state name,
    state description, and protected status if they do not already exist in the database.

    """
    # Create new CaseState objects for each state
    create_safe(db.session, CaseState, state_name='Unspecified', state_description="Unspecified", protected=True)
    create_safe(db.session, CaseState, state_name='In progress', state_description="Case is being investigated")
    create_safe(db.session, CaseState, state_name='Open', state_description="Case is open", protected=True)
    create_safe(db.session, CaseState, state_name='Containment', state_description="Containment is in progress")
    create_safe(db.session, CaseState, state_name='Eradication', state_description="Eradication is in progress")
    create_safe(db.session, CaseState, state_name='Recovery', state_description="Recovery is in progress")
    create_safe(db.session, CaseState, state_name='Post-Incident', state_description="Post-incident phase")
    create_safe(db.session, CaseState, state_name='Reporting', state_description="Reporting is in progress")
    create_safe(db.session, CaseState, state_name='Closed', state_description="Case is closed", protected=True)


def create_safe_review_status():
    """Creates new ReviewStatus objects if they do not already exist.

    This function creates new ReviewStatus objects with the specified status name
    if they do not already exist in the database.
    """
    create_safe(db.session, ReviewStatus, status_name=ReviewStatusList.no_review_required)
    create_safe(db.session, ReviewStatus, status_name=ReviewStatusList.not_reviewed)
    create_safe(db.session, ReviewStatus, status_name=ReviewStatusList.pending_review)
    create_safe(db.session, ReviewStatus, status_name=ReviewStatusList.review_in_progress)
    create_safe(db.session, ReviewStatus, status_name=ReviewStatusList.reviewed)


def create_safe_assets():
    """Creates new AssetsType objects if they do not already exist.

    This function creates new AssetsType objects with the specified asset name,
    asset description, and asset icons if they do not already exist in the database.

    """
    # Create new AssetsType objects for each asset type
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Account",
                           asset_description="Generic Account", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Firewall", asset_description="Firewall",
                           asset_icon_not_compromised="firewall.png", asset_icon_compromised="ioc_firewall.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Linux - Server",
                           asset_description="Linux server", asset_icon_not_compromised="server.png",
                           asset_icon_compromised="ioc_server.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Linux - Computer",
                           asset_description="Linux computer", asset_icon_not_compromised="desktop.png",
                           asset_icon_compromised="ioc_desktop.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Linux Account",
                           asset_description="Linux Account", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Mac - Computer",
                           asset_description="Mac computer", asset_icon_not_compromised="desktop.png",
                           asset_icon_compromised="ioc_desktop.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Phone - Android",
                           asset_description="Android Phone", asset_icon_not_compromised="phone.png",
                           asset_icon_compromised="ioc_phone.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Phone - IOS",
                           asset_description="Apple Phone", asset_icon_not_compromised="phone.png",
                           asset_icon_compromised="ioc_phone.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows - Computer",
                           asset_description="Standard Windows Computer",
                           asset_icon_not_compromised="windows_desktop.png",
                           asset_icon_compromised="ioc_windows_desktop.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows - Server",
                           asset_description="Standard Windows Server", asset_icon_not_compromised="windows_server.png",
                           asset_icon_compromised="ioc_windows_server.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows - DC",
                           asset_description="Domain Controller", asset_icon_not_compromised="windows_server.png",
                           asset_icon_compromised="ioc_windows_server.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Router", asset_description="Router",
                           asset_icon_not_compromised="router.png", asset_icon_compromised="ioc_router.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Switch", asset_description="Switch",
                           asset_icon_not_compromised="switch.png", asset_icon_compromised="ioc_switch.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="VPN", asset_description="VPN",
                           asset_icon_not_compromised="vpn.png", asset_icon_compromised="ioc_vpn.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="WAF", asset_description="WAF",
                           asset_icon_not_compromised="firewall.png", asset_icon_compromised="ioc_firewall.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - Local",
                           asset_description="Windows Account - Local", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - Local - Admin",
                           asset_description="Windows Account - Local - Admin", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - AD",
                           asset_description="Windows Account - AD", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - AD - Admin",
                           asset_description="Windows Account - AD - Admin", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - AD - krbtgt",
                           asset_description="Windows Account - AD - krbtgt", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")
    get_by_value_or_create(db.session, AssetsType, "asset_name", asset_name="Windows Account - AD - Service",
                           asset_description="Windows Account - AD - krbtgt", asset_icon_not_compromised="user.png",
                           asset_icon_compromised="ioc_user.png")


def create_safe_client():
    """Creates a new Client object if it does not already exist.

    This function creates a new Client object with the specified client name
    and client description if it does not already exist in the database.

    """
    # Create a new Client object if it does not already exist
    client = get_or_create(db.session, Client,
                           name="IrisInitialClient")

    return client


def create_safe_auth_model():
    """Creates new Organisation, Group, and User objects if they do not already exist.

    This function creates a new Organisation object with the specified name and description,
    and creates new Group objects with the specified name, description, auto-follow status,
    auto-follow access level, and permissions if they do not already exist in the database.
    It also updates the attributes of the existing Group objects if they have changed.

    """
    # Create new Organisation object
    def_org = get_or_create(db.session, Organisation, org_name="Default Org",
                            org_description="Default Organisation")

    # Create new Administrator Group object
    try:
        gadm = get_or_create(db.session, Group, group_name="Administrators", group_description="Administrators",
                             group_auto_follow=True, group_auto_follow_access_level=CaseAccessLevel.full_access.value,
                             group_permissions=ac_get_mask_full_permissions())

    except exc.IntegrityError:
        db.session.rollback()
        log.warning('Administrator group integrity error. Group permissions were probably changed. Updating.')
        gadm = Group.query.filter(
            Group.group_name == "Administrators"
        ).first()

    # Update Administrator Group object attributes
    if gadm.group_permissions != ac_get_mask_full_permissions():
        gadm.group_permissions = ac_get_mask_full_permissions()

    if gadm.group_auto_follow_access_level != CaseAccessLevel.full_access.value:
        gadm.group_auto_follow_access_level = CaseAccessLevel.full_access.value

    if gadm.group_auto_follow is not True:
        gadm.group_auto_follow = True

    db.session.commit()

    # Create new Analysts Group object
    try:
        ganalysts = get_or_create(db.session, Group, group_name="Analysts", group_description="Standard Analysts",
                                  group_auto_follow=False,
                                  group_auto_follow_access_level=CaseAccessLevel.full_access.value,
                                  group_permissions=ac_get_mask_analyst())

    except exc.IntegrityError:
        db.session.rollback()
        log.warning('Analysts group integrity error. Group permissions were probably changed. Updating.')
        ganalysts = get_group_by_name("Analysts")

    # Update Analysts Group object attributes
    if ganalysts.group_permissions != ac_get_mask_analyst():
        ganalysts.group_permissions = ac_get_mask_analyst()

    if ganalysts.group_auto_follow is not False:
        ganalysts.group_auto_follow = False

    if ganalysts.group_auto_follow_access_level != CaseAccessLevel.full_access.value:
        ganalysts.group_auto_follow_access_level = CaseAccessLevel.full_access.value

    db.session.commit()

    return def_org, gadm, ganalysts


def create_safe_admin(def_org, gadm):
    """Creates a new admin user if one does not already exist.

    This function creates a new admin user with the specified username, email, and password
    if one does not already exist in the database. If an admin user already exists, it updates
    the email address of the existing user if it has changed.

    """
    # Get admin username and email from app config
    admin_username = app.config.get('IRIS_ADM_USERNAME')
    if admin_username is None:
        admin_username = 'administrator'

    admin_email = app.config.get('IRIS_ADM_EMAIL')
    if admin_email is None:
        admin_email = 'administrator@localhost'

    # Check if admin user already exists
    user = User.query.filter(or_(
        User.user == admin_username,
        User.email == admin_email
    )).first()
    password = None

    if not user:
        # Generate a new password if one was not provided in the app config
        password = app.config.get('IRIS_ADM_PASSWORD')
        if password is None:
            password = ''.join(random.choices(string.printable[:-6], k=16))

        log.info(f'Creating first admin user with username "{admin_username}"')

        # Create new User object for admin user
        user = User(
            user=admin_username,
            name=admin_username,
            email=admin_email,
            password=bc.generate_password_hash(password.encode('utf8')).decode('utf8'),
            active=True
        )

        # Generate a new API key if one was not provided in the app config
        api_key = app.config.get('IRIS_ADM_API_KEY')
        if api_key is None:
            api_key = secrets.token_urlsafe(nbytes=64)

        user.api_key = api_key
        db.session.add(user)

        db.session.commit()

        # Add admin user to admin group and default organisation
        add_user_to_group(user_id=user.id, group_id=gadm.group_id)
        add_user_to_organisation(user_id=user.id, org_id=def_org.org_id)

        log.warning(f">>> Administrator password: {password}")

        db.session.commit()

    else:
        if not os.environ.get('IRIS_ADM_PASSWORD'):
            # Prevent leak of user set password in logs
            log.warning(">>> Administrator already exists")

        if user.email != admin_email:
            # Update email address of existing admin user if it has changed
            log.warning(f'Email of administrator will be updated via config to {admin_email}')
            user.email = admin_email
            db.session.commit()

    return user, password


def create_safe_case(user, client, groups):
    """Creates a new case if one does not already exist for the specified client.

    This function creates a new case with the specified name, description, SOC ID, user, and client
    if one does not already exist in the database for the specified client. It also adds the specified
    user and groups to the case with full access level.

    """
    # Check if a case already exists for the client
    case = Cases.query.filter(
        Cases.client_id == client.client_id
    ).first()

    if not case:
        # Create a new case for the client
        case = Cases(
            name="Initial Demo",
            description="This is a demonstration.",
            soc_id="soc_id_demo",
            user=user,
            client_id=client.client_id
        )

        # Validate the case and save it to the database
        case.validate_on_build()
        case.save()

        db.session.commit()

    # Add the specified user and groups to the case with full access level
    for group in groups:
        add_case_access_to_group(group=group,
                                 cases_list=[case.case_id],
                                 access_level=CaseAccessLevel.full_access.value)
        ac_add_user_effective_access(users_list=[user.id],
                                     case_id=1,
                                     access_level=CaseAccessLevel.full_access.value)

    return case


def create_safe_report_types():
    """Creates new ReportType objects if they do not already exist.

    This function creates new ReportType objects with the specified names if they do not already
    exist in the database.

    """
    create_safe(db.session, ReportType, name="Investigation")
    create_safe(db.session, ReportType, name="Activities")


def create_safe_attributes():
    """Creates new Attribute objects if they do not already exist.

    This function creates new Attribute objects with the specified display name, description,
    object type, and content if they do not already exist in the database.

    """
    create_safe_attr(db.session, attribute_display_name='IOC',
                     attribute_description='Defines default attributes for IOCs', attribute_for='ioc',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Events',
                     attribute_description='Defines default attributes for Events', attribute_for='event',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Assets',
                     attribute_description='Defines default attributes for Assets', attribute_for='asset',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Tasks',
                     attribute_description='Defines default attributes for Tasks', attribute_for='task',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Notes',
                     attribute_description='Defines default attributes for Notes', attribute_for='note',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Evidences',
                     attribute_description='Defines default attributes for Evidences', attribute_for='evidence',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Cases',
                     attribute_description='Defines default attributes for Cases', attribute_for='case',
                     attribute_content={})
    create_safe_attr(db.session, attribute_display_name='Customers',
                     attribute_description='Defines default attributes for Customers', attribute_for='client',
                     attribute_content={})


def create_safe_ioctypes():
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="AS",
                        type_description="Autonomous system", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="aba-rtn",
                        type_description="ABA routing transit number",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="account",
                        type_description="Account of any type",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="anonymised",
                        type_description="Anonymised value - described with the anonymisation object via a relationship",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="attachment",
                        type_description="Attachment with external information",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="authentihash",
                        type_description="Authenticode executable signature hash", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{64}", type_validation_expect="64 hexadecimal characters"
                        )
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="boolean",
                        type_description="Boolean value - to be used in objects",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="btc",
                        type_description="Bitcoin Address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="campaign-id",
                        type_description="Associated campaign ID",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="campaign-name",
                        type_description="Associated campaign name",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="cdhash",
                        type_description="An Apple Code Directory Hash, identifying a code-signed Mach-O executable file",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="chrome-extension-id",
                        type_description="Chrome extension id",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="community-id",
                        type_description="a community ID flow hashing algorithm to map multiple traffic monitors into common flow id",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="cookie",
                        type_description="HTTP cookie as often stored on the user web client. This can include authentication cookie or session cookie.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="dash",
                        type_description="Dash Address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="datetime",
                        type_description="Datetime in the ISO 8601 format",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="dkim",
                        type_description="DKIM public key", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="dkim-signature",
                        type_description="DKIM signature", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="dns-soa-email",
                        type_description="RFC1035 mandates that DNS zones should have a SOA (Statement Of Authority) record that contains an email address where a PoC for the domain could be contacted. This can sometimes be used for attribution/linkage between different domains even if protected by whois privacy",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="domain",
                        type_description="A domain name used in the malware",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="domain|ip",
                        type_description="A domain name and its IP address (as found in DNS lookup) separated by a |",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email",
                        type_description="An e-mail address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-attachment",
                        type_description="File name of the email attachment.", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-body",
                        type_description="Email body", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-dst",
                        type_description="The destination email address. Used to describe the recipient when describing an e-mail.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-dst-display-name",
                        type_description="Email destination display name", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-header",
                        type_description="Email header", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-message-id",
                        type_description="The email message ID",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-mime-boundary",
                        type_description="The email mime boundary separating parts in a multipart email",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-reply-to",
                        type_description="Email reply to header",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-src",
                        type_description="The source email address. Used to describe the sender when describing an e-mail.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-src-display-name",
                        type_description="Email source display name",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-subject",
                        type_description="The subject of the email",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-thread-index",
                        type_description="The email thread index header",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="email-x-mailer",
                        type_description="Email x-mailer header",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="favicon-mmh3",
                        type_description="favicon-mmh3 is the murmur3 hash of a favicon as used in Shodan.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename",
                        type_description="Filename", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename-pattern",
                        type_description="A pattern in the name of a file",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|authentihash",
                        type_description="A checksum in md5 format",
                        type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{64}',
                        type_validation_expect="filename|64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|impfuzzy",
                        type_description="Import fuzzy hash - a fuzzy hash created based on the imports in the sample.",
                        type_taxonomy="", )
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|imphash",
                        type_description="Import hash - a hash created based on the imports in the sample.",
                        type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{32}',
                        type_validation_expect="filename|32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|md5",
                        type_description="A filename and an md5 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{32}',
                        type_validation_expect="filename|32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|pehash",
                        type_description="A filename and a PEhash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{40}',
                        type_validation_expect="filename|40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha1",
                        type_description="A filename and an sha1 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{40}',
                        type_validation_expect="filename|40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha224",
                        type_description="A filename and a sha-224 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{56}',
                        type_validation_expect="filename|56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha256",
                        type_description="A filename and an sha256 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{64}',
                        type_validation_expect="filename|64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha3-224",
                        type_description="A filename and an sha3-224 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{56}',
                        type_validation_expect="filename|56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha3-256",
                        type_description="A filename and an sha3-256 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{64}',
                        type_validation_expect="filename|64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha3-384",
                        type_description="A filename and an sha3-384 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{96}',
                        type_validation_expect="filename|96 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha3-512",
                        type_description="A filename and an sha3-512 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{128}',
                        type_validation_expect="filename|128 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha384",
                        type_description="A filename and a sha-384 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{96}',
                        type_validation_expect="filename|96 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha512",
                        type_description="A filename and a sha-512 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{128}',
                        type_validation_expect="filename|128 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha512/224",
                        type_description="A filename and a sha-512/224 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{56}',
                        type_validation_expect="filename|56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|sha512/256",
                        type_description="A filename and a sha-512/256 hash separated by a |", type_taxonomy="",
                        type_validation_regex='.+\|[a-f0-9]{64}',
                        type_validation_expect="filename|64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|ssdeep",
                        type_description="A checksum in ssdeep format",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|tlsh",
                        type_description="A filename and a Trend Micro Locality Sensitive Hash separated by a |",
                        type_taxonomy="",
                        type_validation_regex='.+\|t?[a-f0-9]{35,}',
                        type_validation_expect="filename|at least 35 hexadecimal characters, optionally starting with t1 instead of hexadecimal characters"
                        )
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="filename|vhash",
                        type_description="A filename and a VirusTotal hash separated by a |", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="first-name",
                        type_description="First name of a natural person",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="float",
                        type_description="A floating point value.", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="full-name",
                        type_description="Full name of a natural person",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="gene",
                        type_description="GENE - Go Evtx sigNature Engine",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="git-commit-id",
                        type_description="A git commit ID.", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{40}", type_validation_expect="40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="github-organisation",
                        type_description="A github organisation",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="github-repository",
                        type_description="A github repository",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="github-username",
                        type_description="A github user name",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="hassh-md5",
                        type_description="hassh is a network fingerprinting standard which can be used to identify specific Client SSH implementations. The fingerprints can be easily stored, searched and shared in the form of an MD5 fingerprint.",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="hasshserver-md5",
                        type_description="hasshServer is a network fingerprinting standard which can be used to identify specific Server SSH implementations. The fingerprints can be easily stored, searched and shared in the form of an MD5 fingerprint.",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="hex",
                        type_description="A value in hexadecimal format",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="hostname",
                        type_description="A full host/dnsname of an attacker",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="hostname|port",
                        type_description="Hostname and port number separated by a |", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="http-method",
                        type_description="HTTP method used by the malware (e.g. POST, GET, …).", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="iban",
                        type_description="International Bank Account Number",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="identity-card-number",
                        type_description="Identity card number",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="impfuzzy",
                        type_description="A fuzzy hash of import table of Portable Executable format", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="imphash",
                        type_description="Import hash - a hash created based on the imports in the sample.",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ip-any",
                        type_description="A source or destination IP address of the attacker or C&C server",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ip-dst",
                        type_description="A destination IP address of the attacker or C&C server", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ip-dst|port",
                        type_description="IP destination and port number separated by a |", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ip-src",
                        type_description="A source IP address of the attacker",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ip-src|port",
                        type_description="IP source and port number separated by a |", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ja3-fingerprint-md5",
                        type_description="JA3 is a method for creating SSL/TLS client fingerprints that should be easy to produce on any platform and can be easily shared for threat intelligence.",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="jabber-id",
                        type_description="Jabber ID", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="jarm-fingerprint",
                        type_description="JARM is a method for creating SSL/TLS server fingerprints.", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{62}", type_validation_expect="62 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="kusto-query",
                        type_description="Kusto query - Kusto from Microsoft Azure is a service for storing and running interactive analytics over Big Data.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="link",
                        type_description="Link to an external information",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="mac-address",
                        type_description="Mac address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="mac-eui-64",
                        type_description="Mac EUI-64 address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="malware-sample",
                        type_description="Attachment containing encrypted malware sample", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="malware-type",
                        type_description="Malware type", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="md5",
                        type_description="A checksum in md5 format", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="middle-name",
                        type_description="Middle name of a natural person",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="mime-type",
                        type_description="A media type (also MIME type and content type) is a two-part identifier for file formats and format contents transmitted on the Internet",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="mobile-application-id",
                        type_description="The application id of a mobile application", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="mutex",
                        type_description="Mutex, use the format \BaseNamedObjects<Mutex>", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="named pipe",
                        type_description="Named pipe, use the format .\pipe<PipeName>", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="other",
                        type_description="Other attribute", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="file-path",
                        type_description="Path of file", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pattern-in-file",
                        type_description="Pattern in file that identifies the malware", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pattern-in-memory",
                        type_description="Pattern in memory dump that identifies the malware", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pattern-in-traffic",
                        type_description="Pattern in network traffic that identifies the malware", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pdb",
                        type_description="Microsoft Program database (PDB) path information", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pehash",
                        type_description="PEhash - a hash calculated based of certain pieces of a PE executable file",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{40}", type_validation_expect="40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pgp-private-key",
                        type_description="A PGP private key",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="pgp-public-key",
                        type_description="A PGP public key", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="phone-number",
                        type_description="Telephone Number", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="port",
                        type_description="Port number", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="process-state",
                        type_description="State of a process", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="prtn",
                        type_description="Premium-Rate Telephone Number",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="regkey",
                        type_description="Registry key or value", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="regkey|value",
                        type_description="Registry value + data separated by |",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha1",
                        type_description="A checksum in sha1 format", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{40}", type_validation_expect="40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha224",
                        type_description="A checksum in sha-224 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{56}", type_validation_expect="56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha256",
                        type_description="A checksum in sha256 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{64}", type_validation_expect="64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha3-224",
                        type_description="A checksum in sha3-224 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{56}", type_validation_expect="56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha3-256",
                        type_description="A checksum in sha3-256 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{64}", type_validation_expect="64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha3-384",
                        type_description="A checksum in sha3-384 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{96}", type_validation_expect="96 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha3-512",
                        type_description="A checksum in sha3-512 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{128}", type_validation_expect="128 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha384",
                        type_description="A checksum in sha-384 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{96}", type_validation_expect="96 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha512",
                        type_description="A checksum in sha-512 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{128}", type_validation_expect="128 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha512/224",
                        type_description="A checksum in the sha-512/224 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{56}", type_validation_expect="56 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sha512/256",
                        type_description="A checksum in the sha-512/256 format",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{64}", type_validation_expect="64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="sigma",
                        type_description="Sigma - Generic Signature Format for SIEM Systems", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="size-in-bytes",
                        type_description="Size expressed in bytes",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="snort",
                        type_description="An IDS rule in Snort rule-format",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ssdeep",
                        type_description="A checksum in ssdeep format",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="ssh-fingerprint",
                        type_description="A fingerprint of SSH key material",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="stix2-pattern",
                        type_description="STIX 2 pattern", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-email",
                        type_description="Attack Targets Email(s)",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-external",
                        type_description="External Target Organizations Affected by this Attack", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-location",
                        type_description="Attack Targets Physical Location(s)", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-machine",
                        type_description="Attack Targets Machine Name(s)",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-org",
                        type_description="Attack Targets Department or Organization(s)", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="target-user",
                        type_description="Attack Targets Username(s)",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="telfhash",
                        type_description="telfhash is symbol hash for ELF files, just like imphash is imports hash for PE files.",
                        type_taxonomy="",
                        type_validation_regex="[a-f0-9]{70}", type_validation_expect="70 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="text",
                        type_description="Name, ID or a reference", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="threat-actor",
                        type_description="A string identifying the threat actor",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="tlsh",
                        type_description="A checksum in the Trend Micro Locality Sensitive Hash format",
                        type_taxonomy="",
                        type_validation_regex="^t?[a-f0-9]{35,}",
                        type_validation_expect="at least 35 hexadecimal characters, optionally starting with t1 instead of hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="travel-details",
                        type_description="Travel details", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="twitter-id",
                        type_description="Twitter ID", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="uri",
                        type_description="Uniform Resource Identifier", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="url", type_description="url",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="user-agent",
                        type_description="The user-agent used by the malware in the HTTP request.", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="vhash",
                        type_description="A VirusTotal checksum", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="vulnerability",
                        type_description="A reference to the vulnerability used in the exploit", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="weakness",
                        type_description="A reference to the weakness used in the exploit", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-creation-date",
                        type_description="The date of domain’s creation, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-registrant-email",
                        type_description="The e-mail of a domain’s registrant, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-registrant-name",
                        type_description="The name of a domain’s registrant, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-registrant-org",
                        type_description="The org of a domain’s registrant, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-registrant-phone",
                        type_description="The phone number of a domain’s registrant, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="whois-registrar",
                        type_description="The registrar of the domain, obtained from the WHOIS information.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="windows-scheduled-task",
                        type_description="A scheduled task in windows",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="windows-service-displayname",
                        type_description="A windows service’s displayname, not to be confused with the windows-service-name. This is the name that applications will generally display as the service’s name in applications.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="windows-service-name",
                        type_description="A windows service name. This is the name used internally by windows. Not to be confused with the windows-service-displayname.",
                        type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="x509-fingerprint-md5",
                        type_description="X509 fingerprint in MD5 format", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{32}", type_validation_expect="32 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="x509-fingerprint-sha1",
                        type_description="X509 fingerprint in SHA-1 format", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{40}", type_validation_expect="40 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="x509-fingerprint-sha256",
                        type_description="X509 fingerprint in SHA-256 format", type_taxonomy="",
                        type_validation_regex="[a-f0-9]{64}", type_validation_expect="64 hexadecimal characters")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="xmr",
                        type_description="Monero Address", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="yara",
                        type_description="Yara signature", type_taxonomy="")
    create_safe_limited(db.session, IocType, ["type_name", "type_description"], type_name="zeek",
                        type_description="An NIDS rule in the Zeek rule-format",
                        type_taxonomy="")


def create_safe_os_types():
    create_safe(db.session, OsType, type_name="Windows")
    create_safe(db.session, OsType, type_name="Linux")
    create_safe(db.session, OsType, type_name="AIX")
    create_safe(db.session, OsType, type_name="MacOS")
    create_safe(db.session, OsType, type_name="Apple iOS")
    create_safe(db.session, OsType, type_name="Cisco iOS")
    create_safe(db.session, OsType, type_name="Android")


def create_safe_tlp():
    create_safe(db.session, Tlp, tlp_name="red", tlp_bscolor="danger")
    create_safe(db.session, Tlp, tlp_name="amber", tlp_bscolor="warning")
    create_safe(db.session, Tlp, tlp_name="green", tlp_bscolor="success")
    create_safe(db.session, Tlp, tlp_name="clear", tlp_bscolor="black")
    create_safe(db.session, Tlp, tlp_name="amber+strict", tlp_bscolor="warning")


def create_safe_server_settings():
    if not ServerSettings.query.count():
        create_safe(db.session, ServerSettings,
                    http_proxy="", https_proxy="", prevent_post_mod_repush=False,
                    prevent_post_objects_repush=False,
                    password_policy_min_length="12", password_policy_upper_case=True,
                    password_policy_lower_case=True, password_policy_digit=True,
                    password_policy_special_chars="", enforce_mfa=app.config.get("MFA_ENABLED", False))


def register_modules_pipelines():
    modules = IrisModule.query.with_entities(
        IrisModule.module_name,
        IrisModule.module_config
    ).filter(
        IrisModule.has_pipeline == True
    ).all()

    for module in modules:
        module = module[0]
        inst, _ = instantiate_module_from_name(module)
        if not inst:
            continue

        inst.internal_configure(celery_decorator=celery.task,
                                evidence_storage=None,
                                mod_web_config=module[1])
        status = inst.get_tasks_for_registration()
        if status.is_failure():
            log.warning("Failed getting tasks for module {}".format(module))
            continue

        tasks = status.get_data()
        for task in tasks:
            celery.register_task(task)


def register_default_modules():
    modules = ['iris_vt_module', 'iris_misp_module', 'iris_check_module',
               'iris_webhooks_module', 'iris_intelowl_module']

    for module_name in modules:
        class_, _ = instantiate_module_from_name(module_name)
        is_ready, logs = check_module_health(class_)

        if not is_ready:
            log.info("Attempted to initiate {mod}. Got {err}".format(mod=module_name, err=",".join(logs)))
            return False

        module, logs = register_module(module_name)
        if module is None:
            log.info("Attempted to add {mod}. Got {err}".format(mod=module_name, err=logs))

        else:
            iris_module_disable_by_id(module.id)
            log.info('Successfully registered {mod}'.format(mod=module_name))


def custom_assets_symlinks():
    try:

        source_paths = glob.glob(os.path.join(app.config['ASSET_STORE_PATH'], "*"))

        for store_fullpath in source_paths:

            filename = store_fullpath.split(os.path.sep)[-1]
            show_fullpath = os.path.join(app.config['APP_PATH'], 'app',
                                         app.config['ASSET_SHOW_PATH'].strip(os.path.sep), filename)
            if not os.path.islink(show_fullpath):
                os.symlink(store_fullpath, show_fullpath)
                log.info(f"Created assets img symlink {store_fullpath} -> {show_fullpath}")

    except Exception as e:
        log.error(f"Error: {e}")


def create_directories():
    log.info("Attempting to create data directories")

    for d in ['UPLOADED_PATH', 'TEMPLATES_PATH', 'BACKUP_PATH', 'ASSET_STORE_PATH', 'DATASTORE_PATH']:
        try:
            log.info(f'Creating directory {d}')
            os.makedirs(app.config.get(d), exist_ok=True)
        except OSError as e:
            log.error(f"Failed to create directory {app.config.get(d)}: {e}")
