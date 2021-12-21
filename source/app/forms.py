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

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, IntegerField, BooleanField, \
    widgets, SelectMultipleField, SelectField, DateTimeField
from wtforms.validators import InputRequired, Email, DataRequired, Regexp


class LoginForm(FlaskForm):
    username = StringField(u'Username', validators=[DataRequired()])
    password = PasswordField(u'Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField(u'Name', validators=[DataRequired()])
    username = StringField(u'Username', validators=[DataRequired()])
    password = PasswordField(u'Password', validators=[DataRequired()])
    email = StringField(u'Email', validators=[DataRequired(), Email()])


class SearchForm(FlaskForm):
    search_type = StringField(u'Search Type', validators=[DataRequired()])
    search_value = StringField(u'Search Value', validators=[DataRequired()])


class CustomerForm(FlaskForm):
    customer_name = StringField(u'Customer name', validators=[DataRequired()])


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class AddAssetForm(FlaskForm):
    asset_name = StringField(u'Asset name', validators=[DataRequired()])
    asset_description = StringField(u'Asset description', validators=[DataRequired()])


class AddCustomerForm(FlaskForm):
    customer_name = StringField(u'Customer name', validators=[DataRequired()])


class AddReportTemplateForm(FlaskForm):
    report_name = StringField(u'Report name', validators=[DataRequired()])
    report_description = StringField(u'Report description', validators=[DataRequired()])
    report_name_format = StringField(u'Report name formating', validators=[DataRequired()])
    report_language = SelectField(u'Language', validators=[DataRequired()])
    report_type = SelectField(u'Report Type', validators=[DataRequired()])


class AddUserForm(FlaskForm):
    user_login = StringField(u'Name', validators=[DataRequired()])
    user_name = StringField(u'Username', validators=[DataRequired()])
    user_password = PasswordField(u'Password', validators=[DataRequired()])
    user_email = StringField(u'Email', validators=[DataRequired(), Email()])
    user_isadmin = BooleanField(u'Is admin', default=False)


class ModalAddCaseAssetForm(FlaskForm):
    asset_id = SelectField(u'Asset type', validators=[DataRequired()])


class AddCaseForm(FlaskForm):
    case_name = StringField(u'Case name', validators=[InputRequired()])
    case_description = StringField(u'Case description', validators=[InputRequired()])
    case_soc_id = StringField(u'SOC Ticket')
    case_customer = SelectField(u'Customer', validators=[InputRequired()])

    pipeline = SelectField(u'Analysis pipeline')


class AssetBasicForm(FlaskForm):
    asset_name = StringField(u'Name', validators=[DataRequired()])
    asset_description = TextAreaField(u'Description')
    asset_domain = StringField(u'Domain')
    asset_ip = StringField(u'Domain')
    asset_info = TextAreaField(u'Asset Info')
    asset_compromised = BooleanField(u'Is Compromised')
    asset_type_id = SelectField(u'Asset Type', validators=[DataRequired()])
    analysis_status_id = SelectField(u'Analysis Status', validators=[DataRequired()])


class AssetComputerForm(AssetBasicForm):
    computer_ip = StringField(u'Computer IP')
    computer_os = StringField(u'Computer OS')
    computer_domain = StringField(u'Computer domain')
    is_compromised = BooleanField(u'Is Compromised')


class AssetWinAccountForm(AssetBasicForm):
    account_sid = StringField(u'Account SID')
    account_domain = StringField(u'Account Domain')


class AssetLinAccountForm(AssetBasicForm):
    account_domain = StringField(u'Account Domain')


class CaseEventForm(FlaskForm):
    event_title = StringField(u'Event Title', validators=[DataRequired()])
    event_source = StringField(u'Event Source')
    event_content = TextAreaField(u'Event Description')
    event_raw = TextAreaField(u'Event Raw data')
    event_assets = SelectField(u'Event Asset')
    event_category = SelectField(u'Event Category')
    event_tz = StringField(u'Event Timezone', validators=[DataRequired()])
    event_in_summary = BooleanField(u'Add to summary')
    event_in_graph = BooleanField(u'Display in graph')


class CaseTaskForm(FlaskForm):
    task_title = StringField(u'Task Title', validators=[DataRequired()])
    task_description = TextAreaField(u'Task description')
    task_assignee_id = SelectField(u'Task assignee', validators=[DataRequired()])
    task_status = SelectField(u'Task status')
    task_tags = StringField(u'Task Tags')


class CaseGlobalTaskForm(FlaskForm):
    task_title = StringField(u'Task Title')
    task_description = TextAreaField(u'Task description')
    task_assignee = SelectField(u'Task assignee')
    task_status = SelectField(u'Task status')
    task_tags = StringField(u'Task Tags')


class ModalAddCaseIOCForm(FlaskForm):
    ioc_tags = StringField(u'IOC Tags')
    ioc_value = TextAreaField(u'IOC Value', validators=[DataRequired()])
    ioc_description = TextAreaField(u'IOC Description')
    ioc_type = SelectField(u'IOC Type', validators=[DataRequired()])
    ioc_tlp_id = SelectField(u'IOC TLP', validators=[DataRequired()])


class CaseNoteForm(FlaskForm):
    note_title = StringField(u'Note title', validators=[DataRequired()])
    note_content = StringField(u'Note content')


class AddModuleForm(FlaskForm):
    module_name = StringField(u'Module name', validators=[DataRequired()])


class UpdateModuleParameterForm(FlaskForm):
    module_name = StringField(u'Module name', validators=[DataRequired()])