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
from alembic.config import Config
from alembic import command, context

from sqlalchemy import create_engine, and_
from sqlalchemy_utils import database_exists, create_database

from app import db, bc, app, celery
from app.configuration import SQLALCHEMY_BASE_URI
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.models.cases import Cases, Client
from app.models.models import Role, Languages, User, get_or_create, create_safe, UserRoles, OsType, Tlp, AssetsType, \
    IrisModule, EventCategory, AnalysisStatus, ReportType, IocType, TaskStatus


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

        log.info("Creating base IOC types")
        create_safe_ioctypes()

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

        log.info("Creating base tasks status")
        create_safe_task_status()

        log.info("Running DB migration")

        alembic_cfg = Config(file_='app/alembic.ini')
        alembic_cfg.set_main_option('sqlalchemy.url',  SQLALCHEMY_BASE_URI + 'iris_db')
        command.upgrade(alembic_cfg, 'head')

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


def create_safe_task_status():
    create_safe(db.session, TaskStatus, status_name='To do', status_description="", status_bscolor="danger")
    create_safe(db.session, TaskStatus, status_name='In progress', status_description="", status_bscolor="warning")
    create_safe(db.session, TaskStatus, status_name='On hold', status_description="", status_bscolor="muted")
    create_safe(db.session, TaskStatus, status_name='Done', status_description="", status_bscolor="success")
    create_safe(db.session, TaskStatus, status_name='Canceled', status_description="", status_bscolor="muted")


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


def create_safe_ioctypes():
    create_safe(db.session, IocType, type_name="AS", type_description="Autonomous system", type_taxonomy="")
    create_safe(db.session, IocType, type_name="aba-rtn", type_description="ABA routing transit number",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="account", type_description="Account of any type",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="anonymised",
                type_description="Anonymised value - described with the anonymisation object via a relationship",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="attachment", type_description="Attachment with external information",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="authentihash",
                type_description="Authenticode executable signature hash", type_taxonomy="")
    create_safe(db.session, IocType, type_name="boolean", type_description="Boolean value - to be used in objects",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="btc", type_description="Bitcoin Address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="campaign-id", type_description="Associated campaign ID",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="campaign-name", type_description="Associated campaign name",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="cdhash",
                type_description="An Apple Code Directory Hash, identifying a code-signed Mach-O executable file",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="chrome-extension-id", type_description="Chrome extension id",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="community-id",
                type_description="a community ID flow hashing algorithm to map multiple traffic monitors into common flow id",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="cookie",
                type_description="HTTP cookie as often stored on the user web client. This can include authentication cookie or session cookie.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="dash", type_description="Dash Address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="datetime", type_description="Datetime in the ISO 8601 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="dkim", type_description="DKIM public key", type_taxonomy="")
    create_safe(db.session, IocType, type_name="dkim-signature", type_description="DKIM signature", type_taxonomy="")
    create_safe(db.session, IocType, type_name="dns-soa-email",
                type_description="RFC1035 mandates that DNS zones should have a SOA (Statement Of Authority) record that contains an email address where a PoC for the domain could be contacted. This can sometimes be used for attribution/linkage between different domains even if protected by whois privacy",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="domain", type_description="A domain name used in the malware",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="domain|ip",
                type_description="A domain name and its IP address (as found in DNS lookup) separated by a |",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email", type_description="An e-mail address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-attachment",
                type_description="File name of the email attachment.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-body", type_description="Email body", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-dst",
                type_description="The destination email address. Used to describe the recipient when describing an e-mail.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-dst-display-name",
                type_description="Email destination display name", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-header", type_description="Email header", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-message-id", type_description="The email message ID",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-mime-boundary",
                type_description="The email mime boundary separating parts in a multipart email", type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-reply-to", type_description="Email reply to header",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-src",
                type_description="The source email address. Used to describe the sender when describing an e-mail.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-src-display-name", type_description="Email source display name",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-subject", type_description="The subject of the email",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-thread-index", type_description="The email thread index header",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="email-x-mailer", type_description="Email x-mailer header",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="favicon-mmh3",
                type_description="favicon-mmh3 is the murmur3 hash of a favicon as used in Shodan.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename", type_description="Filename", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename-pattern", type_description="A pattern in the name of a file",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|authentihash", type_description="A checksum in md5 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|impfuzzy",
                type_description="Import fuzzy hash - a fuzzy hash created based on the imports in the sample.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|imphash",
                type_description="Import hash - a hash created based on the imports in the sample.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|md5",
                type_description="A filename and an md5 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|pehash",
                type_description="A filename and a PEhash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha1",
                type_description="A filename and an sha1 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha224",
                type_description="A filename and a sha-224 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha256",
                type_description="A filename and an sha256 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha3-224",
                type_description="A filename and an sha3-224 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha3-256",
                type_description="A filename and an sha3-256 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha3-384",
                type_description="A filename and an sha3-384 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha3-512",
                type_description="A filename and an sha3-512 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha384",
                type_description="A filename and a sha-384 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha512",
                type_description="A filename and a sha-512 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha512/224",
                type_description="A filename and a sha-512/224 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|sha512/256",
                type_description="A filename and a sha-512/256 hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|ssdeep", type_description="A checksum in ssdeep format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|tlsh",
                type_description="A filename and a Trend Micro Locality Sensitive Hash separated by a |",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="filename|vhash",
                type_description="A filename and a VirusTotal hash separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="first-name", type_description="First name of a natural person",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="float", type_description="A floating point value.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="full-name", type_description="Full name of a natural person",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="gene", type_description="GENE - Go Evtx sigNature Engine",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="git-commit-id", type_description="A git commit ID.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="github-organisation", type_description="A github organisation",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="github-repository", type_description="A github repository",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="github-username", type_description="A github user name",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="hassh-md5",
                type_description="hassh is a network fingerprinting standard which can be used to identify specific Client SSH implementations. The fingerprints can be easily stored, searched and shared in the form of an MD5 fingerprint.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="hasshserver-md5",
                type_description="hasshServer is a network fingerprinting standard which can be used to identify specific Server SSH implementations. The fingerprints can be easily stored, searched and shared in the form of an MD5 fingerprint.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="hex", type_description="A value in hexadecimal format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="hostname", type_description="A full host/dnsname of an attacker",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="hostname|port",
                type_description="Hostname and port number separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="http-method",
                type_description="HTTP method used by the malware (e.g. POST, GET, …).", type_taxonomy="")
    create_safe(db.session, IocType, type_name="iban", type_description="International Bank Account Number",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="identity-card-number", type_description="Identity card number",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="impfuzzy",
                type_description="A fuzzy hash of import table of Portable Executable format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="imphash",
                type_description="Import hash - a hash created based on the imports in the sample.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="ip-any",
                type_description="A source or destination IP address of the attacker or C&C server", type_taxonomy="")
    create_safe(db.session, IocType, type_name="ip-dst",
                type_description="A destination IP address of the attacker or C&C server", type_taxonomy="")
    create_safe(db.session, IocType, type_name="ip-dst|port",
                type_description="IP destination and port number separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="ip-src", type_description="A source IP address of the attacker",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="ip-src|port",
                type_description="IP source and port number separated by a |", type_taxonomy="")
    create_safe(db.session, IocType, type_name="ja3-fingerprint-md5",
                type_description="JA3 is a method for creating SSL/TLS client fingerprints that should be easy to produce on any platform and can be easily shared for threat intelligence.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="jabber-id", type_description="Jabber ID", type_taxonomy="")
    create_safe(db.session, IocType, type_name="jarm-fingerprint",
                type_description="JARM is a method for creating SSL/TLS server fingerprints.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="kusto-query",
                type_description="Kusto query - Kusto from Microsoft Azure is a service for storing and running interactive analytics over Big Data.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="link", type_description="Link to an external information",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="mac-address", type_description="Mac address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="mac-eui-64", type_description="Mac EUI-64 address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="malware-sample",
                type_description="Attachment containing encrypted malware sample", type_taxonomy="")
    create_safe(db.session, IocType, type_name="malware-type", type_description="Malware type", type_taxonomy="")
    create_safe(db.session, IocType, type_name="md5", type_description="A checksum in md5 format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="middle-name", type_description="Middle name of a natural person",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="mime-type",
                type_description="A media type (also MIME type and content type) is a two-part identifier for file formats and format contents transmitted on the Internet",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="mobile-application-id",
                type_description="The application id of a mobile application", type_taxonomy="")
    create_safe(db.session, IocType, type_name="mutex",
                type_description="Mutex, use the format \BaseNamedObjects<Mutex>", type_taxonomy="")
    create_safe(db.session, IocType, type_name="named pipe",
                type_description="Named pipe, use the format .\pipe<PipeName>", type_taxonomy="")
    create_safe(db.session, IocType, type_name="other", type_description="Other attribute", type_taxonomy="")
    create_safe(db.session, IocType, type_name="file-path",
                type_description="Path of file", type_taxonomy="")
    create_safe(db.session, IocType, type_name="pattern-in-file",
                type_description="Pattern in file that identifies the malware", type_taxonomy="")
    create_safe(db.session, IocType, type_name="pattern-in-memory",
                type_description="Pattern in memory dump that identifies the malware", type_taxonomy="")
    create_safe(db.session, IocType, type_name="pattern-in-traffic",
                type_description="Pattern in network traffic that identifies the malware", type_taxonomy="")
    create_safe(db.session, IocType, type_name="pdb",
                type_description="Microsoft Program database (PDB) path information", type_taxonomy="")
    create_safe(db.session, IocType, type_name="pehash",
                type_description="PEhash - a hash calculated based of certain pieces of a PE executable file",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="pgp-private-key", type_description="A PGP private key",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="pgp-public-key", type_description="A PGP public key", type_taxonomy="")
    create_safe(db.session, IocType, type_name="phone-number", type_description="Telephone Number", type_taxonomy="")
    create_safe(db.session, IocType, type_name="port", type_description="Port number", type_taxonomy="")
    create_safe(db.session, IocType, type_name="process-state", type_description="State of a process", type_taxonomy="")
    create_safe(db.session, IocType, type_name="prtn", type_description="Premium-Rate Telephone Number",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="regkey", type_description="Registry key or value", type_taxonomy="")
    create_safe(db.session, IocType, type_name="regkey|value", type_description="Registry value + data separated by |",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha1", type_description="A checksum in sha1 format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha224", type_description="A checksum in sha-224 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha256", type_description="A checksum in sha256 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha3-224", type_description="A checksum in sha3-224 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha3-256", type_description="A checksum in sha3-256 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha3-384", type_description="A checksum in sha3-384 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha3-512", type_description="A checksum in sha3-512 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha384", type_description="A checksum in sha-384 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha512", type_description="A checksum in sha-512 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha512/224", type_description="A checksum in the sha-512/224 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sha512/256", type_description="A checksum in the sha-512/256 format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="sigma",
                type_description="Sigma - Generic Signature Format for SIEM Systems", type_taxonomy="")
    create_safe(db.session, IocType, type_name="size-in-bytes", type_description="Size expressed in bytes",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="snort", type_description="An IDS rule in Snort rule-format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="ssdeep", type_description="A checksum in ssdeep format",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="ssh-fingerprint", type_description="A fingerprint of SSH key material",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="stix2-pattern", type_description="STIX 2 pattern", type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-email", type_description="Attack Targets Email(s)",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-external",
                type_description="External Target Organizations Affected by this Attack", type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-location",
                type_description="Attack Targets Physical Location(s)", type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-machine", type_description="Attack Targets Machine Name(s)",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-org",
                type_description="Attack Targets Department or Organization(s)", type_taxonomy="")
    create_safe(db.session, IocType, type_name="target-user", type_description="Attack Targets Username(s)",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="telfhash",
                type_description="telfhash is symbol hash for ELF files, just like imphash is imports hash for PE files.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="text", type_description="Name, ID or a reference", type_taxonomy="")
    create_safe(db.session, IocType, type_name="threat-actor", type_description="A string identifying the threat actor",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="tlsh",
                type_description="A checksum in the Trend Micro Locality Sensitive Hash format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="travel-details", type_description="Travel details", type_taxonomy="")
    create_safe(db.session, IocType, type_name="twitter-id", type_description="Twitter ID", type_taxonomy="")
    create_safe(db.session, IocType, type_name="uri", type_description="Uniform Resource Identifier", type_taxonomy="")
    create_safe(db.session, IocType, type_name="url", type_description="url", type_taxonomy="")
    create_safe(db.session, IocType, type_name="user-agent",
                type_description="The user-agent used by the malware in the HTTP request.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="vhash", type_description="A VirusTotal checksum", type_taxonomy="")
    create_safe(db.session, IocType, type_name="vulnerability",
                type_description="A reference to the vulnerability used in the exploit", type_taxonomy="")
    create_safe(db.session, IocType, type_name="weakness",
                type_description="A reference to the weakness used in the exploit", type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-creation-date",
                type_description="The date of domain’s creation, obtained from the WHOIS information.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-registrant-email",
                type_description="The e-mail of a domain’s registrant, obtained from the WHOIS information.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-registrant-name",
                type_description="The name of a domain’s registrant, obtained from the WHOIS information.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-registrant-org",
                type_description="The org of a domain’s registrant, obtained from the WHOIS information.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-registrant-phone",
                type_description="The phone number of a domain’s registrant, obtained from the WHOIS information.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="whois-registrar",
                type_description="The registrar of the domain, obtained from the WHOIS information.", type_taxonomy="")
    create_safe(db.session, IocType, type_name="windows-scheduled-task", type_description="A scheduled task in windows",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="windows-service-displayname",
                type_description="A windows service’s displayname, not to be confused with the windows-service-name. This is the name that applications will generally display as the service’s name in applications.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="windows-service-name",
                type_description="A windows service name. This is the name used internally by windows. Not to be confused with the windows-service-displayname.",
                type_taxonomy="")
    create_safe(db.session, IocType, type_name="x509-fingerprint-md5",
                type_description="X509 fingerprint in MD5 format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="x509-fingerprint-sha1",
                type_description="X509 fingerprint in SHA-1 format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="x509-fingerprint-sha256",
                type_description="X509 fingerprint in SHA-256 format", type_taxonomy="")
    create_safe(db.session, IocType, type_name="xmr", type_description="Monero Address", type_taxonomy="")
    create_safe(db.session, IocType, type_name="yara", type_description="Yara signature", type_taxonomy="")
    create_safe(db.session, IocType, type_name="zeek", type_description="An NIDS rule in the Zeek rule-format",
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

