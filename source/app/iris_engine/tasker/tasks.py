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

# IMPORTS ------------------------------------------------
import os
import traceback
import urllib.parse
import logging as log

from celery.signals import task_prerun
from flask_login import current_user
from sqlalchemy import case

from app import celery
from app import db, app
from app.blueprints.context.context import update_user_case_ctx
from app.datamgmt.case.case_db import get_case
from app.datamgmt.iris_engine.modules_db import get_pipelines_args_from_name, get_module_config_from_name
from app.iris_engine.connectors.misp4iris import Misp4Iris
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name, configure_module_on_init
from app.iris_engine.utils.common import build_upload_path
from app.iris_engine.reporter.reporter import IrisReporter
from app.iris_engine.utils.tracker import track_activity

from iris_interface.IrisModuleInterface import IrisPipelineTypes

from app.models import CasesDatum, FileContentHash, HashLink, Ioc, CaseEventsAssets, CaseAssets
from app.models.cases import Cases, CasesEvent
from app.util import task_failure, task_success
from iris_interface import IrisInterfaceStatus as IStatus

app.config['timezone'] = 'Europe/Paris'


# CONTENT ------------------------------------------------
@task_prerun.connect
def on_task_init(*args, **kwargs):
    db.engine.dispose()


def task_make_report(caseid):
    """
    Create a report task according to the current case
    :return: JSON report representation
    """
    case = Cases.query \
        .filter(Cases.case_id == caseid) \
        .first()

    if case:
        task_args = {
            "user": current_user.name,
            "user_id": current_user.id,
            "case_name": case.name,
            "case_id": case.case_id,
        }
        report = IrisReporter(None, task_args)
        return report.make_report()

    return False


def task_case_update(module, pipeline, pipeline_args, caseid):
    """
    Update the current case of the current user with fresh data.
    The files should have already been uploaded.
    :return: Tuple (success, errors)
    """
    errors = []
    case = get_case(caseid=caseid)

    if case:
        # We have a case so we can update the current case

        # Build the upload path where the files should be
        fpath = build_upload_path(case_customer=case.client.name,
                                  case_name=urllib.parse.unquote(case.name),
                                  module=module)

        # Check the path is valid and exists
        if fpath:
            if os.path.isdir(fpath):
                # Build task args
                task_args = {
                    "pipeline_args": pipeline_args,
                    "db_name": '',
                    "user": current_user.name,
                    "user_id": current_user.id,
                    "case_name": case.name,
                    "case_id": case.case_id,
                    "path": fpath,
                    "is_update": True
                }

                track_activity("started a new analysis import with pipeline {}".format(pipeline))

                return pipeline_dispatcher(module=module,
                                           pipeline_name=pipeline,
                                           pipeline_type=IrisPipelineTypes.pipeline_type_update,
                                           pipeline_data=task_args)

            return IStatus.I2FileNotFound("Built path was not found ")

        return IStatus.I2UnexpectedResult("Unable to build path")

    else:
        # The user do not have any context so we cannot update
        # Return an error
        errors.append('Current user does not have a valid case in context')
        return IStatus.I2UnexpectedResult("Invalid context")


def task_case_import_from_form(form):
    """
    Handle the creation of the import and feed case according to the data
    received in the request, and passed in the form object
    :param form: Form received within flask
    :return: Tuple (success, errors)
    """
    # The form is already validated so no need to check again
    case = Cases()
    case.name = urllib.parse.quote(form.get('case_name', '', type=str), safe='')
    case.description = form.get('case_description', '', type=str)
    case.soc_id = form.get('case_ticket_id', '', type=str)
    case.gen_report = True  # form.get('case_report', '', type=bool)
    case.client_name = form.get('case_customer', '', type=str)
    case.user_id = current_user.id
    is_empty = form.get('case_empty', '', type=bool)
    pipeline = form.get('pipeline', '', type=str)
    is_check = form.get('is_check', "true", type=str)
    pipeline_mod = ""

    if not is_check:
        try:
            pipeline_mod = pipeline.split("-")[0]
            pipeline_name = pipeline.split("-")[1]
        except Exception as e:
            log.error(e.__str__())
            return IStatus.I2UnexpectedResult('Malformed request')

        if case.validate_on_build():

            # Build the path of uploads
            fpath = build_upload_path(case_customer=case.client_name,
                                      case_name=urllib.parse.unquote(case.name), module=pipeline_mod)

            # Check the path is valid and exists
            if fpath:
                track_activity("Started a new creation {} ({})".format(case.name, case.client_name))
                if os.path.isdir(fpath) and not is_empty:

                    # Save the case to get the case_id
                    case = case.save()

                    # Update the user context
                    update_user_case_ctx()
                    track_activity("Case saved")

                    ppl_config = get_pipelines_args_from_name(pipeline_mod)
                    if not ppl_config:
                        return IStatus.I2Error('Unable to fetch pipeline configuration')

                    pl_args = ppl_config['pipeline_args']
                    pipeline_args = {}
                    for argi in pl_args:

                        arg = argi[0]
                        fetch_arg = form.get('args_' + arg, None, type=str)

                        if argi[1] == 'required' and (not fetch_arg or fetch_arg == ""):
                            return IStatus.I2Error("Pipeline required arguments are not set")

                        if fetch_arg:
                            pipeline_args[arg] = fetch_arg

                        else:
                            pipeline_args[arg] = None

                    # Build task args
                    task_args = {
                        "pipeline_args": pipeline_args,
                        "db_name": '',
                        "user": current_user.name,
                        "user_id": current_user.id,
                        "case_name": case.name,
                        "case_id": case.case_id,
                        "path": fpath,
                        "is_update": False
                    }

                    # Then call the import chain as task chain

                    return pipeline_dispatcher(module=pipeline_mod,
                                               pipeline_name=pipeline,
                                               pipeline_type=IrisPipelineTypes.pipeline_type_update,
                                               pipeline_data=task_args)


                    # return True, [])
                elif is_empty:

                    # Save the case to get the case_id
                    case = case.save()

                    # Update the user context
                    update_user_case_ctx()

                    return IStatus.I2Success

                else:
                    return IStatus.I2FileNotFound("Path not found probably due to previous error")

            return IStatus.I2FileNotFound("Unable to build path")
    try:
        case.validate_on_build()
        case.save()
    except Exception as e:
        return IStatus.I2UnexpectedResult(str(e))

    return IStatus.I2Success


def pipeline_dispatcher(module, pipeline_name, pipeline_type, pipeline_data):
    """
    Dispatch the pipelines according to their types
    :param pipeline_type: Type of pipeline
    :param form: form contained
    :return: IrisInterfaceStatus
    """

    # Retrieve the handler
    mod = instantiate_module_from_name(module_name=module)
    if mod:

        status = configure_module_on_init(mod)
        if status.is_failure():
            return status

        mod_web_config = get_module_config_from_name(module_name=module)

        # mod.internal_configure(celery_decorator=celery.task,
        #                        evidence_storage=EvidenceStorage(),
        #                        mod_web_config=mod_web_config)

        # This will run the task in the Celery context
        result = mod.delay(pipeline_type=pipeline_type,
                           pipeline_data=pipeline_data)

        return IStatus.I2Success('Task queued')

    return IStatus.I2InterfaceNotImplemented("Couldn't instantiate module {}".format(module))

# @celery.task(bind=True)
# def task_files_import(self, task_args):
#     try:
#
#         importer = ImportDispatcher(task_self=self,
#                                     task_args=task_args
#                                     )
#
#         return importer.import_files()
#
#     except Exception as e:
#         traceback.print_exc()
#         return task_failure(
#             user=task_args['user'],
#             initial=self.request.id,
#             case_name=task_args['case_name'],
#             logs=[traceback.print_exc()]
#         )

@celery.task(bind=True)
def task_feed_from_misp(self, import_res, case_id):
    """
    Creates a task that will read data from fresh IrisDB data from new invest (or update).
    The progress is reported to the users through tasks report.
    This task aimed to be the third stage of the tasks chain Iris Import > Iris Feed > Misp Feed.
    If the first and second calls fails, this task will end prematurely.
    :param self: Task instance
    :param import_res: Import results of the call of IrisFeed
    :param case_id: Case ID linked to the tasks
    :return: A task status JSON task_success or task_failure
    """

    try:
        # Create a MISP connexion instance
        m4i = Misp4Iris()
        exec_res = {}

        # Get the case related data from IrisDB, i.e all the hashes linked to the case
        res = CasesDatum.query \
            .with_entities(
            FileContentHash.content_hash
        ).filter(
            CasesDatum.case_id == case_id
        ).join(CasesDatum.hash_link, HashLink.file_content_hash).all()

        if res:
            tab = []
            tot = len(res) * 1.0
            idx = 0.0
            for element in res:

                tab.append(element)

                # Send a batch of 200 hashes to reduce server load
                if len(tab) > 200:

                    # Report progress to user
                    self.update_state(state="PROGRESS",
                                      meta=["Checking {}/{} records. {} % done.".format(idx, tot, (idx / tot) * 100.0)],
                                      )

                    # Send the bash and update DB
                    rt = m4i.search_md5(tab)

                    if rt:
                        # We have result, update the dict
                        # We will bulk update at the end of the method for a better efficiency
                        exec_res.update(rt)

                    # Reset tab to be ready for the next 200 batch
                    tab = []

                # Keep count
                idx += 1.0

            # Bulk update
            FileContentHash.query.filter(
                FileContentHash.content_hash.in_(exec_res)
            ).update(
                {
                    FileContentHash.misp: case(
                        exec_res,
                        value=FileContentHash.content_hash
                    )
                }
                , synchronize_session='fetch')
            db.session.commit()

            return task_success(
                user=import_res.get('user'),
                initial=import_res.get('initial'),
                case_name=import_res.get('case_name'),
                logs=import_res.get('logs'),
                data=exec_res
            )

    except Exception as e:
        traceback.print_exc()
        return task_failure(
            user=import_res.get('user') if import_res.get('user') else "Iris",
            initial=import_res.get('initial') if import_res.get('initial') else "Shadow",
            logs=["Exception while executing task: {}".format(e)],
            data=import_res
        )


def task_update_ioc():
    """
    Nightly task that updates Iris data from MISP
    """
    try:
        ce = CasesEvent.query.all()
        for event in ce:
            try:
                if event.event_asset_id:
                    asset = CaseAssets.query.filter(CaseAssets.asset_id == event.event_asset_id).first()
                    if asset:
                        cea = CaseEventsAssets()
                        cea.case_id = event.case_id
                        cea.event_id = event.event_id
                        cea.asset_id = event.event_asset_id

                        test = CaseEventsAssets.query.filter(
                            CaseEventsAssets.asset_id == event.event_asset_id,
                            CaseEventsAssets.event_id == event.event_id,
                            CaseEventsAssets.case_id == event.case_id
                        ).first()

                        if not test:
                            db.session.add(cea)

                        db.session.commit()

            except Exception as e:
                print(e)

        return "ok"

    except Exception as e:
        traceback.print_exc()
        return task_failure(
            user="Iris",
            initial="Shadow",
            logs=[e],
            data=['Fail']
        )


def task_update_ioc_misp():
    """
    Nightly task that updates Iris data from MISP
    """
    try:
        tot_res = {}
        m4i = Misp4Iris()
        exec_res = {}

        iocs = Ioc.query.with_entities(
            Ioc.ioc_value
        ).filter(
            Ioc.ioc_type == "IP"
        ).all()

        list_iocs = [ioc.ioc_value for ioc in iocs]

        for ll in chunks(list_iocs, 200):
            rt = m4i.search_ip(ll)

            if rt:
                exec_res.update(rt)

        tot_res.update(exec_res)

        if len(exec_res) > 0:
            Ioc.query.filter(
                Ioc.ioc_value.in_(exec_res),
                Ioc.ioc_type == "IP"
            ).update(
                {
                    Ioc.ioc_misp: case(
                        exec_res,
                        value=Ioc.ioc_value
                    )
                }
                , synchronize_session='fetch')
            db.session.commit()

        exec_res = {}

        iocs = Ioc.query.with_entities(
            Ioc.ioc_value
        ).filter(
            Ioc.ioc_type == "Domain"
        ).all()

        list_iocs = [ioc.ioc_value for ioc in iocs]

        for ll in chunks(list_iocs, 200):
            rt = m4i.search_ip(ll)

            if rt:
                exec_res.update(rt)

        tot_res.update(exec_res)

        if len(exec_res) > 0:
            Ioc.query.filter(
                Ioc.ioc_value.in_(exec_res),
                Ioc.ioc_type == "Domain"
            ).update(
                {
                    Ioc.ioc_misp: case(
                        exec_res,
                        value=Ioc.ioc_value
                    )
                }
                , synchronize_session='fetch')
            db.session.commit()

        exec_res = {}

        iocs = Ioc.query.with_entities(
            Ioc.ioc_value
        ).filter(
            Ioc.ioc_type == "Filename"
        ).all()

        list_iocs = [ioc.ioc_value for ioc in iocs]

        for ll in chunks(list_iocs, 200):
            rt = m4i.search_ip(ll)

            if rt:
                exec_res.update(rt)

        tot_res.update(exec_res)

        if len(exec_res) > 0:
            Ioc.query.filter(
                Ioc.ioc_value.in_(exec_res),
                Ioc.ioc_type == "Filename"
            ).update(
                {
                    Ioc.ioc_misp: case(
                        exec_res,
                        value=Ioc.ioc_value
                    )
                }
                , synchronize_session='fetch')
            db.session.commit()

        return tot_res

    except Exception as e:
        traceback.print_exc()
        return task_failure(
            user="Iris",
            initial="Shadow",
            logs=[e],
            data=['Fail']
        )


def task_pull_misp_all():
    """
    Nightly task that updates Iris data from MISP
    :return:
    """
    try:

        m4i = Misp4Iris()
        exec_res = {}

        lene = FileContentHash.query.count()

        tab = []
        tot = lene * 1.0
        idx = 0.0
        for element in FileContentHash.query.distinct(FileContentHash.content_hash).all():
            tab.append(element)
            if len(tab) >= 200:

                # self.update_state(state="PROGRESS",
                #                meta=["Checking {}/{} records. {} %".format(idx, tot, (idx / tot) * 100.0)],
                #             )
                print('\rChecking {}/{} records. {} %'.format(idx, tot, (idx / tot) * 100.0), end="")
                rt = m4i.search_md5(tab)
                if rt:
                    # print(rt)
                    exec_res.update(rt)

                tab = []

            idx += 1

        # Bulk update
        FileContentHash.query.filter(
            FileContentHash.content_hash.in_(exec_res)
        ).update(
            {
                FileContentHash.misp: case(
                    exec_res,
                    value=FileContentHash.content_hash
                )
            }
            , synchronize_session='fetch')
        db.session.commit()

        return exec_res

    except Exception as e:
        traceback.print_exc()
        return task_failure(
            user="Iris",
            initial="Shadow",
            logs=[e],
            data=['Fail']
        )


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
