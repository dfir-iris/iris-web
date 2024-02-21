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
import base64
import datetime
from flask_login import current_user

from app import db, app
from app.models import IrisHook
from app.models import IrisModule
from app.models import IrisModuleHook
from app.models.authorization import User

log = app.logger


def iris_module_exists(module_name):
    return IrisModule.query.filter(IrisModule.module_name == module_name).first() is not None


def iris_module_name_from_id(module_id):
    data = IrisModule.query.filter(IrisModule.id == module_id).first()
    if data:
        return data.module_name
    return None


def iris_module_add(module_name, module_human_name, module_description,
                    module_version, interface_version, has_pipeline, pipeline_args, module_config, module_type):
    im = IrisModule()
    im.module_name = module_name
    im.module_human_name = module_human_name
    im.module_description = module_description
    im.module_version = module_version
    im.interface_version = interface_version
    im.date_added = datetime.datetime.utcnow()
    im.has_pipeline = has_pipeline
    im.pipeline_args = pipeline_args
    im.module_config = module_config
    im.added_by_id = current_user.id if current_user else User.query.first().id
    im.is_active = True
    im.module_type = module_type

    try:
        db.session.add(im)
        db.session.commit()
    except Exception:
        return None

    return im


def is_mod_configured(mod_config):
    missing_params = []
    for config in mod_config:
        if config['mandatory'] and ("value" not in config or config["value"] == ""):
            missing_params.append(config['param_name'])

    return len(missing_params) == 0, missing_params


def iris_module_save_parameter(mod_id, mod_config, parameter, value, section=None):
    data = IrisModule.query.filter(IrisModule.id == mod_id).first()
    if data is None:
        return False

    index = 0
    for config in mod_config:

        if config['param_name'] == parameter:
            if config['type'] == "bool":
                if isinstance(value, str):
                    value = bool(value.lower() == "true")
                elif isinstance(value, bool):
                    value = bool(value)
                else:
                    value = False

            mod_config[index]["value"] = value
            data.module_config = mod_config
            db.session.commit()
            return True

        index += 1

    return False


def iris_module_enable_by_id(module_id):
    data = IrisModule.query.filter(IrisModule.id == module_id).first()
    if data:
        data.is_active = True
        db.session.commit()
        return True
    return False


def iris_module_disable_by_id(module_id):
    data = IrisModule.query.filter(IrisModule.id == module_id).first()
    if data:
        data.is_active = False
        db.session.commit()
        return True
    return False


def iris_modules_list():
    data = IrisModule.query.with_entities(
        IrisModule.id, IrisModule.module_human_name, IrisModule.has_pipeline, IrisModule.module_version,
        IrisModule.interface_version, IrisModule.date_added, User.name, IrisModule.is_active, IrisModule.module_config
    ).join(User).all()

    ret = []
    for element in data:
        dict_element = element._asdict()
        mod_configured, _ = is_mod_configured(element.module_config)
        if not mod_configured:
            iris_module_disable_by_id(element.id)
            dict_element['configured'] = False
        else:
            dict_element['configured'] = True

        ret.append(dict_element)

    return ret


def get_module_from_id(module_id):
    data = IrisModule.query.filter(IrisModule.id == module_id).first()

    return data


def get_module_config_from_id(module_id):
    data = IrisModule.query.with_entities(
        IrisModule.module_config,
        IrisModule.module_human_name,
        IrisModule.module_name
    ).filter(
        IrisModule.id == module_id
    ).first()

    return data.module_config, data.module_human_name, data.module_name


def get_module_config_from_name(module_name):
    data = IrisModule.query.with_entities(
        IrisModule.module_config,
        IrisModule.module_human_name
    ).filter(
        IrisModule.module_name == module_name
    ).first()

    return data


def get_module_config_from_hname(module_name):
    data = IrisModule.query.with_entities(
        IrisModule.module_config
    ).filter(
        IrisModule.module_human_name == module_name
    ).first()

    if data:
        return data[0]
    else:
        return None


def get_pipelines_args_from_name(module_name):
    data = IrisModule.query.with_entities(
        IrisModule.pipeline_args
    ).filter(
        IrisModule.module_name == module_name
    ).first()

    return data.pipeline_args


def delete_module_from_id(module_id):
    IrisModuleHook.query.filter(
        IrisModuleHook.module_id == module_id
    ).delete()
    db.session.commit()

    IrisModule.query.filter(IrisModule.id == module_id).delete()
    db.session.commit()
    return True


def modules_list_pipelines():
    return IrisModule.query.filter(
        IrisModule.has_pipeline == True,
        IrisModule.is_active == True
    ).with_entities(
        IrisModule.module_name,
        IrisModule.pipeline_args
    ).all()


def module_list_hooks_view():
    return IrisModuleHook.query.with_entities(
        IrisModuleHook.id,
        IrisModule.module_name,
        IrisModule.is_active,
        IrisHook.hook_name,
        IrisHook.hook_description,
        IrisModuleHook.is_manual_hook
    ).join(
        IrisModuleHook.module
    ).join(
        IrisModuleHook.hook
    ).all()


def module_list_available_hooks():
    return IrisHook.query.with_entities(
        IrisHook.id,
        IrisHook.hook_name,
        IrisHook.hook_description
    ).all()


def parse_module_parameter(module_parameter):
    try:

        param = base64.b64decode(module_parameter).decode('utf-8')
        mod_id = param.split('##')[0]
        param_name = param.split('##')[1]

    except Exception as e:
        log.exception(e)
        return None, None, None, None

    mod_config, mod_name, mod_iname = get_module_config_from_id(mod_id)

    parameter = None
    for param in mod_config:
        if param_name == param['param_name']:
            parameter = param
            break

    if not parameter:
        return None, None, None, None

    return mod_config, mod_id, mod_name, mod_iname, parameter
