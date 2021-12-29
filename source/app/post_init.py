#!/usr/bin/env python3
#
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

import logging as log
import random
import secrets
import string
import os

from sqlalchemy import create_engine, and_
from sqlalchemy_utils import database_exists, create_database

from app import db, bc, app, celery
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.models.cases import Cases, Client
from app.models.models import Role, Languages, User, get_or_create, create_safe, UserRoles, OsType, Tlp, AssetsType, \
    IrisModule, EventCategory, AnalysisStatus, ReportType


def run_post_init(development=False):
    log.info("Running post initiation steps")

    if os.getenv("IRIS_WORKER") is None:
        # Setup database before everything
        log.info("Creating all Iris tables")
        db.create_all(bind=None)
        db.session.commit()

        log.info("Creating Celery metatasks tables")
        create_safe_db(db_name="iris_tasks")
        db.create_all(bind="iris_tasks")
        db.session.commit()

        log.info("Creating base languages")
        create_safe_languages()

        log.info("Creating base user roles")
        create_safe_roles()

        log.info("Creating base os types")
        create_safe_os_types()

        log.info("Creating base report types")
        create_safe_report_types()

        log.info("Creating base TLP")
        create_safe_tlp()

        log.info("Creating base events categories")
        create_safe_events_cats()

        log.info("Creating base assets")
        create_safe_assets()

        log.info("Creating base analysis status")
        create_safe_analysis_status()

    log.info("Registering modules pipeline tasks")
    register_modules_pipelines()

    if os.getenv("IRIS_WORKER") is None:
        log.info("Creating first administrative user")
        admin = create_safe_admin()

        log.info("Creating demo client")
        client = create_safe_client()

        log.info("Creating demo case")
        case = create_safe_case(
            user=admin,
            client=client
        )

    if development:
        if os.getenv("IRIS_WORKER") is None:
            log.warning("=================================")
            log.warning("| THIS IS DEVELOPMENT INSTANCE  |")
            log.warning("|    DO NOT USE IN PRODUCTION    |")
            log.warning("=================================")

            # Do "dev" stuff here


def create_safe_db(db_name):
    engine = create_engine(app.config["SQALCHEMY_PIGGER_URI"] + db_name)

    if not database_exists(engine.url):
        create_database(engine.url)

    engine.dispose()


def create_safe_languages():
    create_safe(db.session, Languages, name="french", code="FR")
    create_safe(db.session, Languages, name="english", code="EN")
    create_safe(db.session, Languages, name="german", code="DE")


def create_safe_events_cats():
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


def create_safe_roles():
    get_or_create(db.session, Role, name='administrator')
    get_or_create(db.session, Role, name='investigator')
    get_or_create(db.session, Role, name='viewer')


def create_safe_analysis_status():
    create_safe(db.session, AnalysisStatus, name='Unspecified')
    create_safe(db.session, AnalysisStatus, name='To be done')
    create_safe(db.session, AnalysisStatus, name='Started')
    create_safe(db.session, AnalysisStatus, name='Pending')
    create_safe(db.session, AnalysisStatus, name='Canceled')
    create_safe(db.session, AnalysisStatus, name='Done')


def create_safe_assets():
    get_or_create(db.session, AssetsType, asset_name="Account", asset_description="Generic Account")
    get_or_create(db.session, AssetsType, asset_name="Firewall", asset_description="Firewall")
    get_or_create(db.session, AssetsType, asset_name="Linux - Server", asset_description="Linux server")
    get_or_create(db.session, AssetsType, asset_name="Linux - Computer", asset_description="Linux computer")
    get_or_create(db.session, AssetsType, asset_name="Linux Account", asset_description="Linux Account")
    get_or_create(db.session, AssetsType, asset_name="Mac - Computer", asset_description="Mac computer")
    get_or_create(db.session, AssetsType, asset_name="Phone - Android", asset_description="Android Phone")
    get_or_create(db.session, AssetsType, asset_name="Phone - IOS", asset_description="Apple Phone")
    get_or_create(db.session, AssetsType, asset_name="Windows - Computer", asset_description="Standard Windows Computer")
    get_or_create(db.session, AssetsType, asset_name="Windows - Server", asset_description="Standard Windows Server")
    get_or_create(db.session, AssetsType, asset_name="Windows - DC", asset_description="Domain Controller")
    get_or_create(db.session, AssetsType, asset_name="Router", asset_description="Router")
    get_or_create(db.session, AssetsType, asset_name="Switch", asset_description="Switch")
    get_or_create(db.session, AssetsType, asset_name="VPN", asset_description="VPN")
    get_or_create(db.session, AssetsType, asset_name="WAF", asset_description="WAF")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - Local",
                                          asset_description="Windows Account - Local")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - Local - Admin",
                                          asset_description="Windows Account - Local - Admin")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - AD",
                                          asset_description="Windows Account - AD")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - AD - Admin",
                                          asset_description="Windows Account - AD - Admin")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - AD - krbtgt",
                                          asset_description="Windows Account - AD - krbtgt")
    get_or_create(db.session, AssetsType, asset_name="Windows Account - AD - Service",
                                          asset_description="Windows Account - AD - krbtgt")


def create_safe_client():
    client = get_or_create(db.session, Client,
                           name="IrisInitialClient")

    return client


def create_safe_admin():
    user = User.query.filter(
        User.user == "administrator",
        User.name == "administrator",
        User.email == "administrator@iris.local"
    ).first()
    if not user:
        password = os.environ.get('IRIS_ADM_PASSWORD', ''.join(random.choice(string.printable[:-6]) for i in range(16)))
        user = User(user="administrator",
                    name="administrator",
                    email="administrator@iris.local",
                    password=bc.generate_password_hash(password.encode('utf8')).decode('utf8'),
                    active=True
                    )
        user.api_key = secrets.token_urlsafe(nbytes=64)
        db.session.add(user)

        db.session.commit()

        log.warning(">>> Administrator password: {pwd}".format(pwd=password))

        ur = UserRoles()
        ur.user_id = user.id
        ur.role_id = Role.query.with_entities(Role.id).filter(Role.name == 'administrator').first()
        db.session.add(ur)

        db.session.commit()
    else:
        log.warning(">>> Administrator already exists")

    return user


def create_safe_case(user, client):
    case = Cases.query.filter(
            Cases.client_id == client.client_id
    ).first()

    if not case:
        case = Cases(
            name="Initial Demo",
            description="This is a demonstration.",
            soc_id="soc_id_demo",
            gen_report=False,
            user=user,
            client_id=client.client_id
        )

        case.validate_on_build()
        case.save()

        db.session.commit()

    return case


def create_safe_report_types():
    create_safe(db.session, ReportType, name="Investigation")
    create_safe(db.session, ReportType, name="Activities")


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


def register_modules_pipelines():
    modules = IrisModule.query.with_entities(
        IrisModule.module_name,
        IrisModule.module_config
    ).filter(
        IrisModule.has_pipeline == True
    ).all()

    for module in modules:
        module = module[0]
        inst = instantiate_module_from_name(module)
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

