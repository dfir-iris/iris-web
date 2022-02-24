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
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name, configure_module_on_init, \
    pipeline_dispatcher
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

                pipeline_dispatcher.delay(module=module,
                                          pipeline_type=IrisPipelineTypes.pipeline_type_update,
                                          pipeline_data=task_args,
                                          init_user=current_user.name,
                                          caseid=caseid)

                return IStatus.I2Success('Pipeline task queued')

            return IStatus.I2FileNotFound("Built path was not found ")

        return IStatus.I2UnexpectedResult("Unable to build path")

    else:
        # The user do not have any context so we cannot update
        # Return an error
        errors.append('Current user does not have a valid case in context')
        return IStatus.I2UnexpectedResult("Invalid context")


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
