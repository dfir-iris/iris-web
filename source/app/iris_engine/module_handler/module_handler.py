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
import importlib

from app import app, configuration

from app.datamgmt.iris_engine.modules_db import iris_module_exists, iris_module_add, modules_list_pipelines, \
     get_module_config_from_hname
from iris_interface import IrisInterfaceStatus as IStatus
import logging


log = logging.getLogger('iris')


def check_module_compatibility(module_version):
    return True


def check_pipeline_args(pipelines_args):
    """
    Verify that the pipeline arguments are correct and can be used later on
    :param pipelines_args: JSON pipelines
    :return: Status
    """
    logs = []
    has_error = False

    if type(pipelines_args) != dict:
        return True, ["Error - Pipeline args are not json"]

    if not pipelines_args.get("pipeline_internal_name"):
        has_error = True
        logs.append("Error - pipeline_internal_name missing from pipeline config")

    if not pipelines_args.get("pipeline_human_name"):
        has_error = True
        logs.append("Error - pipeline_human_name missing from pipeline config")

    if not pipelines_args.get("pipeline_args"):
        has_error = True
        logs.append("Error - pipeline_args missing from pipeline config")

    if not pipelines_args.get("pipeline_update_support"):
        has_error = True
        logs.append("Error - pipeline_update_support missing from pipeline config")

    if not pipelines_args.get("pipeline_import_support"):
        has_error = True
        logs.append("Error - pipeline_import_support missing from pipeline config")

    return has_error, logs


def check_module_health(module_instance):
    """
    Returns a status on the health of the module.
    A non healthy module will not be imported
    :param module_instance: Instance of the module to check
    :return: Status
    """
    logs = []

    def dup_logs(message):
        logs.append(message)
        log.info(message)

    if not module_instance:
        return False, ['Error - cannot instantiate the module. Check server logs']

    try:
        dup_logs("Testing module")
        dup_logs("Module name : {}".format(module_instance.get_module_name()))

        if not (app.config.get('MODULES_INTERFACE_MIN_VERSION') <= module_instance.get_interface_version() <= app.config.get('MODULES_INTERFACE_MAX_VERSION')):
            log.critical("Module interface no compatible with server. Expected "
                         f"{app.config.get('MODULES_INTERFACE_MIN_VERSION')} <= module "
                         f"<= {app.config.get('MODULES_INTERFACE_MAX_VERSION')}")

            return False, logs.append("Module interface no compatible with server. Expected "
                                      f"{app.config.get('MODULES_INTERFACE_MIN_VERSION')} <= module "
                                      f"<= {app.config.get('MODULES_INTERFACE_MAX_VERSION')}")

        dup_logs("Module interface version : {}".format(module_instance.get_interface_version()))

        module_type = module_instance.get_module_type()
        if module_type not in ["pipeline", "processor"]:
            log.critical(f"Unrecognised module type. Expected pipeline or processor, got {module_type}")
            return False, logs.append(f"Unrecognised module type. Expected pipeline or processor, got {module_type}")

        dup_logs("Module type : {}".format(module_instance.get_module_type()))

        if not module_instance.is_providing_pipeline() and module_type == 'pipeline':
            log.critical("Module of type pipeline has no pipelines")
            return False, logs.append("Error - Module of type pipeline has not pipelines")

        if module_instance.is_providing_pipeline():
            dup_logs("Module has pipeline : {}".format(module_instance.is_providing_pipeline()))
            # Check the pipelines config health
            has_error, llogs = check_pipeline_args(module_instance.pipeline_get_info())

            logs.extend(llogs)

            if has_error:
                return False, logs

        dup_logs("Module health validated")
        return module_instance.is_ready(), logs

    except Exception as e:
        log.error(e.__str__())
        return False, logs.append(e.__str__())


def instantiate_module_from_name(module_name):
    """
    Instantiate a module from a name. The method is not Exception protected.
    Caller need to take care of it failing.
    :param module_name: Name of the module to register
    :return: Class instance or None
    """
    mod_root_interface = importlib.import_module(module_name)
    if not mod_root_interface:
        return None

    # The whole concept is based on the fact that the root module provides an __iris_module_interface
    # variable pointing to the interface class with which Iris can talk to
    mod_interface = importlib.import_module("{}.{}".format(module_name,
                                                           mod_root_interface.__iris_module_interface))
    if not mod_interface:
        return None

    # Now get a handle on the interface class
    cl_interface = getattr(mod_interface, mod_root_interface.__iris_module_interface)
    if not cl_interface:
        return None

    # Try to instantiate the class
    mod_inst = cl_interface()

    return mod_inst


def configure_module_on_init(module_instance):
    """
    Configure a module after instantiation, with the current configuration
    :param module_instance: Instance of the module
    :return: IrisInterfaceStatus
    """
    if not module_instance:
        return IStatus.I2InterfaceNotImplemented('Module not found')

    return IStatus.I2ConfigureSuccess


def preset_init_mod_config(mod_config):
    """
    Prefill the configuration with default one
    :param mod_config: Configuration
    :return: Tuple
    """
    index = 0
    for config in mod_config:

        if config.get('default') is not None:
            mod_config[index]["value"] = config.get('default')
        index += 1

    return mod_config


def get_mod_config_by_name(module_name):
    """
    Returns a module configurationn based on its name
    :param: module_name: Name of the module
    :return: IrisInterfaceStatus
    """
    data = get_module_config_from_hname(module_name)

    if not data:
        return IStatus.I2InterfaceNotReady(message="Module not registered")

    return IStatus.I2Success(data=data)


def register_module(module_name):
    """
    Register a module into IRIS
    :param module_name: Name of the module to register
    """

    if not module_name:
        log.error("Provided module has no names")
        return False, ["Module has no names"]

    try:

        mod_inst = instantiate_module_from_name(module_name=module_name)
        if not mod_inst:
            log.error("Module could not be instantiated")
            return False, ["Module could not be instantiated"]

        if iris_module_exists(module_name=module_name):
            log.error("Module already exists in Iris")
            return False, ["Module already exists in Iris"]

        # Auto parse the configuration and fill with default
        mod_config = preset_init_mod_config(mod_inst.get_init_configuration())

        success = iris_module_add(module_name=module_name,
                                  module_human_name=mod_inst.get_module_name(),
                                  module_description=mod_inst.get_module_description(),
                                  module_config=mod_config,
                                  module_version=mod_inst.get_module_version(),
                                  interface_version=mod_inst.get_module_version(),
                                  has_pipeline=mod_inst.is_providing_pipeline(),
                                  pipeline_args=mod_inst.pipeline_get_info(),
                                  module_type=mod_inst.get_module_type()
                                  )

        if not success:
            return False, ["Unable to register module"]

    except Exception as e:
        return False, ["Fatal - {}".format(e.__str__())]

    return True, ["Module registered"]


def list_available_pipelines():
    """
    Return a list of available pipelines by requesting the DB
    """
    data = modules_list_pipelines()

    return data

