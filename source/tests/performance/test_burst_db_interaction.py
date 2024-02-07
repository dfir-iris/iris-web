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


from unittest import TestCase

import logging
import random
from datetime import datetime
from datetime import timedelta

from app import db
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_notes_db import add_note
from app.datamgmt.case.case_notes_db import add_note_group
from app.datamgmt.manage.manage_users_db import create_user
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.cases import Client
from app.models.models import CaseEventsAssets
from app.models.authorization import User
from app.post_init import run_post_init
from tests.clean_database import clean_db


class TestBurstDBInteraction(TestCase):
    def setUp(self) -> None:
        logging.info('SetUp called')
        clean_db()
        run_post_init()

    def tearDown(self) -> None:
        logging.info('Teardown called')
        clean_db()

    @staticmethod
    def _create_burst_users(random_nb: int):
        user_name = "User "
        user_login = "user_"
        user_password = "user_"
        user_email = "user_"
        for i in range(0, random_nb):
            create_user(
                user_name=f"{user_name}{str(i)}",
                user_login=f"{user_login}{str(i)}",
                user_password=f"{user_password}{str(i)}",
                user_email=f"{user_email}{str(i)}",
                user_isadmin=(i % 2 == 0)
            )

    @staticmethod
    def _create_burst_clients(clients_nb: int):
        for i in range(clients_nb):
            client = Client(f"client_{str(i)}")
            db.session.add(client)

        db.session.commit()

    @staticmethod
    def _create_burst_cases(users_nb: int, client_nb: int, cases_nb: int):
        for i in range(cases_nb):
            logging.info(f"Creating case #{str(i)}")
            asset_l = []

            case = Cases(
                name=f"Test {str(i)}",
                description=f"Testing case number {str(i)}",
                soc_id=f"SOC{str(i)}",
                gen_report=False,
                user=(User.query.filter(User.id == random.randrange(1, users_nb)).first()),
                client_name=f"client_{str(random.randrange(1, client_nb))}"
            )

            case.validate_on_build()
            case.save()

            for ii in range(random.randrange(5, 10)):
                ng = add_note_group(
                    group_title=f"Group #{str(ii)}",
                    caseid=case.case_id,
                    userid=random.randrange(1, users_nb),
                    creationdate=datetime.utcnow()
                )

                for iii in range(random.randrange(2, 8)):
                    add_note(
                        note_title=f"Note #{str(ii)}",
                        creation_date=datetime.utcnow(),
                        user_id=random.randrange(1, users_nb),
                        caseid=case.case_id,
                        group_id=ng.group_id
                    )

            for ii in range(random.randrange(6, 140)):
                asset = create_asset(
                    asset_name=f"asset_{str(ii)}",
                    asset_description=f"My asset {str(i)}",
                    asset_ip='',
                    asset_info='',
                    asset_compromised=(ii % 2 == 0),
                    asset_type=random.randrange(1, 19),
                    asset_domain='',
                    date_added=datetime.utcnow(),
                    date_update=datetime.utcnow(),
                    caseid=case.case_id,
                    user_id=random.randrange(1, users_nb),
                    analysis_status=random.randrange(1, 5)
                )

                asset_l.append(asset.asset_id)

            for ii in range(random.randrange(10, 350)):
                event = CasesEvent()
                event.case_id = case.case_id
                event.user_id = random.randrange(1, users_nb)
                event.event_raw = ""
                event.event_content = f"My event content @{str(ii)}"
                event.event_title = f"My event title @{str(ii)}"
                event.event_tags = ''
                event.event_color = ''
                event.event_date = datetime.utcnow()
                event.event_added = datetime.utcnow()

                db.session.add(event)
                db.session.commit()
                for iii in range(random.randrange(0, 5)):
                    cea = CaseEventsAssets()
                    cea.asset_id = asset_l[random.randrange(len(asset_l))]
                    cea.event_id = event.event_id
                    cea.case_id = case.case_id

                    db.session.add(cea)

                db.session.commit()

    @staticmethod
    def random_date(start, end):
        delta = end - start
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
        random_second = random.randrange(int_delta)
        return start + timedelta(seconds=random_second)

    @staticmethod
    def update_dates():
        d1 = datetime.strptime('1/1/2008 1:30 PM', '%m/%d/%Y %I:%M %p')
        d2 = datetime.strptime('12/12/2021 4:50 AM', '%m/%d/%Y %I:%M %p')
        events = CasesEvent.query.all()
        for event in events:
            event.event_date = datetime.utcnow()
            logging.info(f"Updating event {event.event_title}")
        db.session.commit()

    def test_burst_creation(self):
        start_time = datetime.utcnow()
        logging.info(f"Test started at: {start_time.__str__()}")

        logging.info('Creating random users')
        self._create_burst_users(154)

        logging.info('Creating random clients')
        self._create_burst_clients(68)

        logging.info('Creating random cases')
        self._create_burst_cases(154, 68, 1489)

        end_time = datetime.utcnow()
        logging.info(f"Test ended at: {end_time.__str__()}")
        logging.info(f"Elapsed time: {(end_time - start_time).__str__()}")

