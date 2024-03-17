#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
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

# IMPORTS ------------------------------------------------

# VARS ---------------------------------------------------

# CONTENT ------------------------------------------------
import logging as log
import os
from datetime import datetime

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from app.datamgmt.reporter.report_db import export_case_json_for_report
from app.iris_engine.utils.common import IrisJinjaEnv
from docx_generator.docx_generator import DocxGenerator
from docx_generator.exceptions import rendering_error
from flask_login import current_user
from sqlalchemy import desc

from app import app
from app.datamgmt.activities.activities_db import get_auto_activities
from app.datamgmt.activities.activities_db import get_manual_activities
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.reporter.report_db import export_case_json
from app.models import AssetsType
from app.models import CaseAssets
from app.models import CaseEventsAssets
from app.models import CaseReceivedFile
from app.models import CaseTemplateReport
from app.models import CasesEvent
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocLink
from app.iris_engine.reporter.ImageHandler import ImageHandler

LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
log.basicConfig(level=log.INFO, format=LOG_FORMAT)


class IrisReportMaker(object):
    """
    IRIS generical report maker
    """

    def __init__(self, tmp_dir, report_id, caseid, safe_mode=False):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._case_info = {}
        self._caseid = caseid
        self.safe_mode = safe_mode

    def get_case_info(self, doc_type):
        """Returns case information

        Args:
            doc_type (_type_): Investigation or Activities report

        Returns:
            _type_: case info
        """
        if doc_type == 'Investigation':
            case_info = self._get_case_info()
        elif doc_type == 'Activities':
            case_info = self._get_activity_info()
        else:
            log.error("Unknown report type")
            return None
        return case_info

    def _get_activity_info(self):
        auto_activities = get_auto_activities(self._caseid)
        manual_activities = get_manual_activities(self._caseid)
        case_info_in = self._get_case_info()

        # Format information and generate the activity report #
        doc_id = "{}".format(datetime.utcnow().strftime("%y%m%d_%H%M"))

        case_info = {
            'auto_activities': auto_activities,
            'manual_activities': manual_activities,
            'date': datetime.utcnow(),
            'gen_user': current_user.name,
            'case': {'name': case_info_in['case'].get('name'),
                     'open_date': case_info_in['case'].get('open_date'),
                     'for_customer': case_info_in['case'].get('client').get('customer_name'),
                     'client': case_info_in['case'].get('client')
                     },
            'doc_id': doc_id
        }

        return case_info

    def _get_case_info(self):
        """
        Retrieve information of the case
        :return:
        """
        case_info = export_case_json(self._caseid)

        # Get customer, user and case title
        case_info['doc_id'] = IrisReportMaker.get_docid()
        case_info['user'] = current_user.name

        # Set date
        case_info['date'] = datetime.utcnow().strftime("%Y-%m-%d")

        return case_info

    @staticmethod
    def get_case_summary(caseid):
        """
        Retrieve the case summary from thehive
        :return:
        """

        _crc32, descr = case_get_desc_crc(caseid)

        # return IrisMakeDocReport.markdown_to_text(descr)
        return descr

    @staticmethod
    def get_case_files(caseid):
        """
        Retrieve the list of files with their hashes
        :return:
        """
        files = CaseReceivedFile.query.filter(
            CaseReceivedFile.case_id == caseid
        ).with_entities(
            CaseReceivedFile.filename,
            CaseReceivedFile.date_added,
            CaseReceivedFile.file_hash,
            CaseReceivedFile.custom_attributes
        ).order_by(
            CaseReceivedFile.date_added
        ).all()

        if files:
            return [row._asdict() for row in files]

        else:
            return []

    @staticmethod
    def get_case_timeline(caseid):
        """
        Retrieve the case timeline
        :return:
        """
        timeline = CasesEvent.query.filter(
            CasesEvent.case_id == caseid
        ).order_by(
            CasesEvent.event_date
        ).all()

        cache_id = {}
        ras = {}
        tim = []
        for row in timeline:
            ras = row
            setattr(ras, 'asset', None)

            as_list = CaseEventsAssets.query.with_entities(
                CaseAssets.asset_id,
                CaseAssets.asset_name,
                AssetsType.asset_name.label('type')
            ).filter(
                CaseEventsAssets.event_id == row.event_id
            ).join(CaseEventsAssets.asset, CaseAssets.asset_type).all()

            alki = []
            for asset in as_list:
                alki.append("{} ({})".format(asset.asset_name, asset.type))

            setattr(ras, 'asset', "\r\n".join(alki))

            tim.append(ras)

        return tim

    @staticmethod
    def get_case_ioc(caseid):
        """
        Retrieve the list of IOC linked to the case
        :return:
        """
        res = IocLink.query.distinct().with_entities(
            Ioc.ioc_value,
            Ioc.ioc_type,
            Ioc.ioc_description,
            Ioc.ioc_tags,
            Ioc.custom_attributes
        ).filter(
            IocLink.case_id == caseid
        ).join(IocLink.ioc).order_by(Ioc.ioc_type).all()

        if res:
            return [row._asdict() for row in res]

        else:
            return []

    @staticmethod
    def get_case_assets(caseid):
        """
        Retrieve the assets linked ot the case
        :return:
        """
        ret = []

        res = CaseAssets.query.distinct().with_entities(
            CaseAssets.asset_id,
            CaseAssets.asset_name,
            CaseAssets.asset_description,
            CaseAssets.asset_compromised.label('compromised'),
            AssetsType.asset_name.label("type"),
            CaseAssets.custom_attributes,
            CaseAssets.asset_tags
        ).filter(
            CaseAssets.case_id == caseid
        ).join(
            CaseAssets.asset_type
        ).order_by(desc(CaseAssets.asset_compromised)).all()

        for row in res:
            row = row._asdict()
            row['light_asset_description'] = row['asset_description']

            ial = IocAssetLink.query.with_entities(
                Ioc.ioc_value,
                Ioc.ioc_type,
                Ioc.ioc_description
            ).filter(
                IocAssetLink.asset_id == row['asset_id']
            ).join(
                IocAssetLink.ioc
            ).all()

            if ial:
                row['asset_ioc'] = [row._asdict() for row in ial]
            else:
                row['asset_ioc'] = []

            ret.append(row)

        return ret

    @staticmethod
    def get_docid():
        return "{}".format(
            datetime.utcnow().strftime("%y%m%d_%H%M"))

    @staticmethod
    def markdown_to_text(markdown_string):
        """
        Converts a markdown string to plaintext
        """
        return markdown_string.replace('\n', '</w:t></w:r><w:r/></w:p><w:p><w:r><w:t xml:space="preserve">').replace(
            '#', '')


class IrisMakeDocReport(IrisReportMaker):
    """
    Generates a DOCX report for the case
    """

    def __init__(self, tmp_dir, report_id, caseid, safe_mode=False):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._case_info = {}
        self._caseid = caseid
        self._safe_mode = safe_mode

    def generate_doc_report(self, doc_type):
        """
        Actually generates the report
        :return:
        """
        if doc_type == 'Investigation':
            case_info = self._get_case_info()
        elif doc_type == 'Activities':
            case_info = self._get_activity_info()
        else:
            log.error("Unknown report type")
            return None

        report = CaseTemplateReport.query.filter(CaseTemplateReport.id == self._report_id).first()

        name = "{}".format("{}.docx".format(report.naming_format))
        name = name.replace("%code_name%", case_info['doc_id'])
        name = name.replace('%customer%', case_info['case']['client']['customer_name'])
        name = name.replace('%case_name%', case_info['case'].get('name'))
        name = name.replace('%date%', datetime.utcnow().strftime("%Y-%m-%d"))
        output_file_path = os.path.join(self._tmp, name)

        try:

            if not self._safe_mode:
                image_handler = ImageHandler(template=None, base_path='/')
            else:
                image_handler = None

            generator = DocxGenerator(image_handler=image_handler)
            generator.generate_docx("/",
                                    os.path.join(app.config['TEMPLATES_PATH'], report.internal_reference),
                                    case_info,
                                    output_file_path
                                    )

            return output_file_path, ""

        except rendering_error.RenderingError as e:

            return None, e.__str__()

    def _get_activity_info(self):
        auto_activities = get_auto_activities(self._caseid)
        manual_activities = get_manual_activities(self._caseid)
        case_info_in = self._get_case_info()

        # Format information and generate the activity report #
        doc_id = "{}".format(datetime.utcnow().strftime("%y%m%d_%H%M"))

        case_info = {
            'auto_activities': auto_activities,
            'manual_activities': manual_activities,
            'date': datetime.utcnow(),
            'gen_user': current_user.name,
            'case': {'name': case_info_in['case'].get('name'),
                     'open_date': case_info_in['case'].get('open_date'),
                     'for_customer': case_info_in['case'].get('for_customer'),
                     'client': case_info_in['case'].get('client')
                     },
            'doc_id': doc_id
        }

        return case_info

    def _get_case_info(self):
        """
        Retrieve information of the case
        :return:
        """
        case_info = export_case_json_for_report(self._caseid)

        # Get customer, user and case title
        case_info['doc_id'] = IrisMakeDocReport.get_docid()
        case_info['user'] = current_user.name

        # Set date
        case_info['date'] = datetime.utcnow().strftime("%Y-%m-%d")

        return case_info

    @staticmethod
    def get_case_summary(caseid):
        """
        Retrieve the case summary from thehive
        :return:
        """

        _crc32, descr = case_get_desc_crc(caseid)

        # return IrisMakeDocReport.markdown_to_text(descr)
        return descr

    @staticmethod
    def get_case_files(caseid):
        """
        Retrieve the list of files with their hashes
        :return:
        """
        files = CaseReceivedFile.query.filter(
            CaseReceivedFile.case_id == caseid
        ).with_entities(
            CaseReceivedFile.filename,
            CaseReceivedFile.date_added,
            CaseReceivedFile.file_hash,
            CaseReceivedFile.custom_attributes
        ).order_by(
            CaseReceivedFile.date_added
        ).all()

        if files:
            return [row._asdict() for row in files]

        else:
            return []

    @staticmethod
    def get_case_timeline(caseid):
        """
        Retrieve the case timeline
        :return:
        """
        timeline = CasesEvent.query.filter(
            CasesEvent.case_id == caseid
        ).order_by(
            CasesEvent.event_date
        ).all()

        cache_id = {}
        ras = {}
        tim = []
        for row in timeline:
            ras = row
            setattr(ras, 'asset', None)

            as_list = CaseEventsAssets.query.with_entities(
                CaseAssets.asset_id,
                CaseAssets.asset_name,
                AssetsType.asset_name.label('type')
            ).filter(
                CaseEventsAssets.event_id == row.event_id
            ).join(CaseEventsAssets.asset, CaseAssets.asset_type).all()

            alki = []
            for asset in as_list:
                alki.append("{} ({})".format(asset.asset_name, asset.type))

            setattr(ras, 'asset', "\r\n".join(alki))

            tim.append(ras)

        return tim

    @staticmethod
    def get_case_ioc(caseid):
        """
        Retrieve the list of IOC linked to the case
        :return:
        """
        res = IocLink.query.distinct().with_entities(
            Ioc.ioc_value,
            Ioc.ioc_type,
            Ioc.ioc_description,
            Ioc.ioc_tags,
            Ioc.custom_attributes
        ).filter(
            IocLink.case_id == caseid
        ).join(IocLink.ioc).order_by(Ioc.ioc_type).all()

        if res:
            return [row._asdict() for row in res]

        else:
            return []

    @staticmethod
    def get_case_assets(caseid):
        """
        Retrieve the assets linked ot the case
        :return:
        """
        ret = []

        res = CaseAssets.query.distinct().with_entities(
            CaseAssets.asset_id,
            CaseAssets.asset_name,
            CaseAssets.asset_description,
            CaseAssets.asset_compromise_status_id.label('compromise_status'),
            AssetsType.asset_name.label("type"),
            CaseAssets.custom_attributes,
            CaseAssets.asset_tags
        ).filter(
            CaseAssets.case_id == caseid
        ).join(
            CaseAssets.asset_type
        ).order_by(desc(CaseAssets.asset_compromise_status_id)).all()

        for row in res:
            row = row._asdict()
            row['light_asset_description'] = row['asset_description']

            ial = IocAssetLink.query.with_entities(
                Ioc.ioc_value,
                Ioc.ioc_type,
                Ioc.ioc_description
            ).filter(
                IocAssetLink.asset_id == row['asset_id']
            ).join(
                IocAssetLink.ioc
            ).all()

            if ial:
                row['asset_ioc'] = [row._asdict() for row in ial]
            else:
                row['asset_ioc'] = []

            ret.append(row)

        return ret

    @staticmethod
    def get_docid():
        return "{}".format(
            datetime.utcnow().strftime("%y%m%d_%H%M"))

    @staticmethod
    def markdown_to_text(markdown_string):
        """
        Converts a markdown string to plaintext
        """
        return markdown_string.replace('\n', '</w:t></w:r><w:r/></w:p><w:p><w:r><w:t xml:space="preserve">').replace(
            '#', '')


class IrisMakeMdReport(IrisReportMaker):
    """
    Generates a MD report for the case
    """

    def __init__(self, tmp_dir, report_id, caseid, safe_mode=False):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._case_info = {}
        self._caseid = caseid
        self.safe_mode = safe_mode

    def generate_md_report(self, doc_type):
        """
        Generate report file
        """
        case_info = self.get_case_info(doc_type)
        if case_info is None:
            return None

        # Get file extension
        report = CaseTemplateReport.query.filter(
            CaseTemplateReport.id == self._report_id).first()

        _, report_format = os.path.splitext(report.internal_reference)

        case_info['case']['for_customer'] = f"{case_info['case'].get('client').get('customer_name')} (legacy::use client.customer_name)"

        # Prepare report name
        name = "{}".format(("{}" + str(report_format)).format(report.naming_format))
        name = name.replace("%code_name%", case_info['doc_id'])
        name = name.replace(
            '%customer%', case_info['case'].get('client').get('customer_name'))
        name = name.replace('%case_name%', case_info['case'].get('name'))
        name = name.replace('%date%', datetime.utcnow().strftime("%Y-%m-%d"))

        # Build output file
        output_file_path = os.path.join(self._tmp, name)

        try:
            env = IrisJinjaEnv()
            env.filters = app.jinja_env.filters
            template = env.from_string(
               open(os.path.join(app.config['TEMPLATES_PATH'], report.internal_reference)).read())
            output_text = template.render(case_info)

            # Write the result in the output file
            with open(output_file_path, 'w', encoding="utf-8") as html_file:
                html_file.write(output_text)

        except Exception as e:
            log.exception("Error while generating report: {}".format(e))
            return None, e.__str__()

        return output_file_path, 'Report generated'


class QueuingHandler(log.Handler):
    """A thread safe logging.Handler that writes messages into a queue object.

       Designed to work with LoggingWidget so log messages from multiple
       threads can be shown together in a single ttk.Frame.

       The standard logging.QueueHandler/logging.QueueListener can not be used
       for this because the QueueListener runs in a private thread, not the
       main thread.

       Warning:  If multiple threads are writing into this Handler, all threads
       must be joined before calling logging.shutdown() or any other log
       destinations will be corrupted.
    """

    def __init__(self, *args, task_self, message_queue, **kwargs):
        """Initialize by copying the queue and sending everything else to superclass."""
        log.Handler.__init__(self, *args, **kwargs)
        self.message_queue = message_queue
        self.task_self = task_self

    def emit(self, record):
        """Add the formatted log message (sans newlines) to the queue."""
        self.message_queue.append(self.format(record).rstrip('\n'))
        self.task_self.update_state(state='PROGRESS',
                                    meta=list(self.message_queue))
