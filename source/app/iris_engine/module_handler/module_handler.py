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
import traceback

import base64
import importlib
from flask_login import current_user
from packaging import version
from pickle import dumps
from pickle import loads
from sqlalchemy import and_

from app import app
from app import celery
from app import db
from app.datamgmt.iris_engine.modules_db import get_module_config_from_hname
from app.datamgmt.iris_engine.modules_db import iris_module_add
from app.datamgmt.iris_engine.modules_db import iris_module_exists
from app.datamgmt.iris_engine.modules_db import modules_list_pipelines
from app.models import IrisHook
from app.models import IrisModule
from app.models import IrisModuleHook
from app.util import hmac_sign
from app.util import hmac_verify
from iris_interface import IrisInterfaceStatus as IStatus

log = app.logger


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

        if type(module_instance.get_interface_version()) != str:
            mod_interface_version = str(module_instance.get_interface_version())
        else:
            mod_interface_version = module_instance.get_interface_version()

        if not (version.parse(app.config.get('MODULES_INTERFACE_MIN_VERSION'))
                <= version.parse(mod_interface_version)
                <= version.parse(app.config.get('MODULES_INTERFACE_MAX_VERSION'))):
            log.critical("Module interface no compatible with server. Expected "
                         f"{app.config.get('MODULES_INTERFACE_MIN_VERSION')} <= module "
                         f"<= {app.config.get('MODULES_INTERFACE_MAX_VERSION')}")
            logs.append("Module interface no compatible with server. Expected "
                        f"{app.config.get('MODULES_INTERFACE_MIN_VERSION')} <= module "
                        f"<= {app.config.get('MODULES_INTERFACE_MAX_VERSION')}")

            return False, logs

        dup_logs("Module interface version : {}".format(module_instance.get_interface_version()))

        module_type = module_instance.get_module_type()
        if module_type not in ["module_pipeline", "module_processor"]:
            log.critical(f"Unrecognised module type. Expected module_pipeline or module_processor, got {module_type}")
            logs.append(f"Unrecognised module type. Expected module_pipeline or module_processor, got {module_type}")
            return False, logs

        dup_logs("Module type : {}".format(module_instance.get_module_type()))

        if not module_instance.is_providing_pipeline() and module_type == 'pipeline':
            log.critical("Module of type pipeline has no pipelines")
            logs.append("Error - Module of type pipeline has not pipelines")
            return False, logs

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
        log.exception("Error while checking module health")
        log.error(e.__str__())
        logs.append(e.__str__())
        return False, logs


def instantiate_module_from_name(module_name):
    """
    Instantiate a module from a name. The method is not Exception protected.
    Caller need to take care of it failing.
    :param module_name: Name of the module to register
    :return: Class instance or None
    """
    try:
        mod_root_interface = importlib.import_module(module_name)
        if not mod_root_interface:
            return None
    except Exception as e:
        msg = f"Could not import root module {module_name}: {e}"
        log.error(msg)
        return None, msg
    # The whole concept is based on the fact that the root module provides an __iris_module_interface
    # variable pointing to the interface class with which Iris can talk to
    try:
        mod_interface = importlib.import_module("{}.{}".format(module_name,
                                                           mod_root_interface.__iris_module_interface))
    except Exception as e:
        msg = f"Could not import module {module_name}: {e}"
        log.error(msg)
        return None, msg

    if not mod_interface:
        return None

    # Now get a handle on the interface class
    try:
        cl_interface = getattr(mod_interface, mod_root_interface.__iris_module_interface)
    except Exception as e:
        msg = f"Could not get handle on the interface class of module {module_name}: {e}"
        log.error(msg)
        return None, msg

    if not cl_interface:
        return None, ''

    # Try to instantiate the class
    try:
        mod_inst = cl_interface()
    except Exception as e:
        msg = f"Could not instantiate the class for module {module_name}: {e}"
        log.error(msg)
        return None, msg

    return mod_inst, 'Success'


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
        return None, "Module has no names"

    try:

        mod_inst, _ = instantiate_module_from_name(module_name=module_name)
        if not mod_inst:
            log.error("Module could not be instantiated")
            return None, "Module could not be instantiated"

        if iris_module_exists(module_name=module_name):
            log.warning("Module already exists in Iris")
            return None, "Module already exists in Iris"

        # Auto parse the configuration and fill with default
        log.info('Parsing configuration')
        mod_config = preset_init_mod_config(mod_inst.get_init_configuration())

        log.info('Adding module')
        module = iris_module_add(module_name=module_name,
                                  module_human_name=mod_inst.get_module_name(),
                                  module_description=mod_inst.get_module_description(),
                                  module_config=mod_config,
                                  module_version=mod_inst.get_module_version(),
                                  interface_version=mod_inst.get_interface_version(),
                                  has_pipeline=mod_inst.is_providing_pipeline(),
                                  pipeline_args=mod_inst.pipeline_get_info(),
                                  module_type=mod_inst.get_module_type()
                                  )

        if module is None:
            return None, "Unable to register module"

        if mod_inst.get_module_type() == 'module_processor':
            mod_inst.register_hooks(module_id=module.id)

    except Exception as e:
        return None, "Fatal - {}".format(e.__str__())

    return module, "Module registered"


def iris_update_hooks(module_name, module_id):
    """
    Update hooks upon settings update
    :param module_name: Name of the module to update
    :param module_id: ID of the module to update
    """

    if not module_name:
        log.error("Provided module has no names")
        return False, ["Module has no names"]

    try:
        mod_inst,_ = instantiate_module_from_name(module_name=module_name)
        if not mod_inst:
            log.error("Module could not be instantiated")
            return False, ["Module could not be instantiated"]

        if mod_inst.get_module_type() == 'module_processor':
            mod_inst.register_hooks(module_id=module_id)

    except Exception as e:
        return False, ["Fatal - {}".format(e.__str__())]

    return True, ["Module updated"]


def register_hook(module_id: int, iris_hook_name: str, manual_hook_name: str = None,
                  run_asynchronously: bool = True):
    """
    Register a new hook into IRIS. The hook_name should be a well-known hook to IRIS. iris_hooks table can be
    queried, or by default they are declared in iris source code > source > app > post_init.

    If is_manual_hook is set, the hook is triggered by user action and not automatically. If set, the iris_hook_name
    should be a manual hook (aka begin with on_manual_trigger_) otherwise an error is raised.

    If run_asynchronously is set (default), the action will be sent to RabbitMQ and processed asynchronously.
    If set to false, the action is immediately done, which means it needs to be quick otherwise the request will be
    pending and user experience degraded.

    :param module_id: Module ID to register
    :param iris_hook_name: Well-known hook name to register to
    :param manual_hook_name: The name of the hook displayed in the UI, if is_manual_hook is set
    :param run_asynchronously: Set to true to queue the module action in rabbitmq
    :return: Tuple
    """

    module = IrisModule.query.filter(IrisModule.id == module_id).first()
    if not module:
        return False, [f'Module ID {module_id} not found']

    is_manual_hook = False
    if "on_manual_trigger_" in iris_hook_name:
        is_manual_hook = True
        if not manual_hook_name:
            # Set default hook name
            manual_hook_name = f"{module.module_name}::{iris_hook_name}"

    hook = IrisHook.query.filter(IrisHook.hook_name == iris_hook_name).first()
    if not hook:
        return False, [f"Hook {iris_hook_name} is unknown"]

    if not isinstance(is_manual_hook, bool):
        return False, [f"Expected bool for is_manual_hook but got {type(is_manual_hook)}"]

    if not isinstance(run_asynchronously, bool):
        return False, [f"Expected bool for run_asynchronously but got {type(run_asynchronously)}"]

    mod = IrisModuleHook.query.filter(
        IrisModuleHook.hook_id == hook.id,
        IrisModuleHook.module_id == module_id,
        IrisModuleHook.manual_hook_ui_name == manual_hook_name
    ).first()
    if not mod:
        imh = IrisModuleHook()
        imh.is_manual_hook = is_manual_hook
        imh.wait_till_return = False
        imh.run_asynchronously = run_asynchronously
        imh.max_retry = 0
        imh.manual_hook_ui_name = manual_hook_name
        imh.hook_id = hook.id
        imh.module_id = module_id

        try:
            db.session.add(imh)
            db.session.commit()
        except Exception as e:
            return False, [str(e)]

        return True, [f"Hook {iris_hook_name} registered"]

    else:
        return True, [f"Hook {iris_hook_name} already registered"]


def deregister_from_hook(module_id: int, iris_hook_name: str):
    """
    Deregister from an existing hook. The hook_name should be a well-known hook to IRIS. No error are thrown if the
    hook wasn't register in the first place

    :param module_id: Module ID to deregister
    :param iris_hook_name: hook_name to deregister from
    :return: IrisInterfaceStatus object
    """
    log.info(f'Deregistering module #{module_id} from {iris_hook_name}')
    hooks = IrisModuleHook.query.filter(
        IrisModuleHook.module_id == module_id,
        IrisHook.hook_name == iris_hook_name,
        IrisModuleHook.hook_id == IrisHook.id
    ).all()
    if hooks:
        for hook in hooks:
            log.info(f'Deregistered module #{module_id} from {iris_hook_name}')
            db.session.delete(hook)

    return True, ['Hook deregistered']


@celery.task(bind=True)
def task_hook_wrapper(self, module_name, hook_name, hook_ui_name, data, init_user, caseid):
    """
    Wrap a hook call into a Celery task to run asynchronously

    :param self: Task instance
    :param module_name: Module name to instanciate and call
    :param hook_name: Name of the hook which was triggered
    :param hook_ui_name: Name of the UI hook so module knows which hook was called
    :param data: Data associated to the hook to process
    :param init_user: User initiating the task
    :param caseid: Case associated
    :return: A task status JSON task_success or task_failure
    """
    try:
        # Data is serialized, so deserialized
        signature, pdata = data.encode("utf-8").split(b" ")
        is_verified = hmac_verify(signature, pdata)
        if is_verified is False:
            log.warning("data argument has not been correctly serialised")
            raise Exception('Unable to instantiate target module. Data has not been correctly serialised')

        deser_data = loads(base64.b64decode(pdata))

    except Exception as e:
        log.exception(e)
        raise Exception(e)

    try:

        _obj = None
        # The received object will most likely be cleared when handled by the task,
        # so we need to attach it to the session in the task
        _obj = []
        if isinstance(deser_data, list):
            _obj = []
            for dse_data in deser_data:
                obj = db.session.merge(dse_data)
                db.session.commit()
                _obj.append(obj)

        elif isinstance(deser_data, str) or isinstance(deser_data, int):
            _obj = [deser_data]

        elif isinstance(deser_data, dict):
            _obj = [deser_data]

        else:
            _obj_a = db.session.merge(deser_data)
            db.session.commit()
            _obj.append(_obj_a)

    except Exception as e:
        log.exception(e)
        raise Exception(e)

    log.info(f'Calling module {module_name} for hook {hook_name}')

    try:
        mod_inst, _ = instantiate_module_from_name(module_name=module_name)

        if mod_inst:
            task_status = mod_inst.hooks_handler(hook_name, hook_ui_name, data=_obj)

            # Recommit the changes made by the module
            db.session.commit()

        else:
            raise Exception('Unable to instantiate target module')

    except Exception as e:
        msg = f"Failed to run hook {hook_name} with module {module_name}. Error {str(e)}"
        log.critical(msg)
        log.exception(e)
        task_status = IStatus.I2Error(message=msg, logs=[traceback.format_exc()], user=init_user, caseid=caseid)

    return task_status


def call_modules_hook(hook_name: str, data: any, caseid: int = None, hook_ui_name: str = None, module_name: str = None) -> any:
    """
    Calls modules which have registered the specified hook

    :raises: Exception if hook name doesn't exist. This shouldn't happen
    :param hook_name: Name of the hook to call
    :param hook_ui_name: UI name of the hook
    :param data: Data associated with the hook
    :param module_name: Name of the module to call. If None, all modules matching the hook will be called
    :param caseid: Case ID
    :return: Any
    """
    hook = IrisHook.query.filter(IrisHook.hook_name == hook_name).first()
    if not hook:
        log.critical(f'Hook name {hook_name} not found')
        raise Exception(f'Hook name {hook_name} not found')

    if hook_ui_name:
        condition = and_(
            IrisModule.is_active == True,
            IrisModuleHook.hook_id == hook.id,
            IrisModuleHook.manual_hook_ui_name == hook_ui_name
        )
    else:
        condition = and_(
            IrisModule.is_active == True,
            IrisModuleHook.hook_id == hook.id
        )

    if module_name:
        condition = and_(
            condition,
            IrisModule.module_name == module_name
        )

    modules = IrisModuleHook.query.with_entities(
        IrisModuleHook.run_asynchronously,
        IrisModule.module_name,
        IrisModuleHook.manual_hook_ui_name
    ).filter(condition).join(
        IrisModule, IrisModuleHook.module_id == IrisModule.id
    ).all()

    for module in modules:
        if module.run_asynchronously and "on_preload_" not in hook_name:
            log.info(f'Calling module {module.module_name} asynchronously for hook {hook_name} :: {hook_ui_name}')
            # We cannot directly pass the sqlalchemy in data, as it needs to be serializable
            # So pass a dumped instance and then rebuild on the task side
            ser_data = base64.b64encode(dumps(data))
            ser_data_auth = hmac_sign(ser_data) + b" " + ser_data
            task_hook_wrapper.delay(module_name=module.module_name, hook_name=hook_name,
                                    hook_ui_name=module.manual_hook_ui_name, data=ser_data_auth.decode("utf8"),
                                    init_user=current_user.name, caseid=caseid)

        else:
            # Direct call. Should be fast
            log.info(f'Calling module {module.module_name} for hook {hook_name}')

            try:
                was_list = True
                # The data passed on to the module hook is expected to be a list
                # So we make sure it's the case or adapt otherwise
                if not isinstance(data, list):
                    data_list = [data]
                    was_list = False
                else:
                    data_list = data

                mod_inst, _ = instantiate_module_from_name(module_name=module.module_name)
                status = mod_inst.hooks_handler(hook_name, module.manual_hook_ui_name, data=data_list)

            except Exception as e:
                log.critical(f"Failed to run hook {hook_name} with module {module.module_name}. Error {str(e)}")
                continue

            if status.is_success():
                data_result = status.get_data()
                if not was_list:
                    if not isinstance(data_result, list):
                        log.critical(f"Error getting data result from hook {hook_name}: "
                                     f"A list is expected, instead got a {type(data_result)}")
                        continue
                    else:
                        # We fetch the first elt here because we want to get back to the old type
                        data = data_result[0]
                else:
                    data = data_result

    return data


def list_available_pipelines():
    """
    Return a list of available pipelines by requesting the DB
    """
    data = modules_list_pipelines()

    return data


@celery.task(bind=True)
def pipeline_dispatcher(self, module_name, hook_name, pipeline_type, pipeline_data, init_user, caseid):
    """
    Dispatch the pipelines according to their types
    :param pipeline_type: Type of pipeline
    :return: IrisInterfaceStatus
    """

    # Retrieve the handler
    mod, _ = instantiate_module_from_name(module_name=module_name)
    if mod:

        status = configure_module_on_init(mod)
        if status.is_failure():
            return status

        # This will run the task in the Celery context
        return mod.pipeline_handler(pipeline_type=pipeline_type,
                                    pipeline_data=pipeline_data)

    return IStatus.I2InterfaceNotImplemented("Couldn't instantiate module {}".format(module_name))
