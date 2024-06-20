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
from wtforms import BooleanField
from wtforms import PasswordField
from wtforms import SelectField
from wtforms import SelectMultipleField
from wtforms import StringField
from wtforms import TextAreaField
from wtforms import widgets
from wtforms.fields.simple import SubmitField
from wtforms.validators import DataRequired
from wtforms.validators import Email
from wtforms.validators import InputRequired


class LoginForm(FlaskForm):
    username = StringField(u'Username', validators=[DataRequired()])
    password = PasswordField(u'Password', validators=[DataRequired()])


class MFASetupForm(FlaskForm):
    token = StringField('Token', validators=[DataRequired()])
    mfa_secret = StringField('MFA Secret')
    user_password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Verify')


class RegisterForm(FlaskForm):
    name = StringField(u'Name', validators=[DataRequired()])
    username = StringField(u'Username', validators=[DataRequired()])
    password = PasswordField(u'Password', validators=[DataRequired()])
    email = StringField(u'Email', validators=[DataRequired(), Email()])


class SearchForm(FlaskForm):
    search_type = StringField(u'Search Type', validators=[DataRequired()])
    search_value = StringField(u'Search Value', validators=[DataRequired()])


class AddCustomerForm(FlaskForm):
    customer_name = StringField(u'Customer name', validators=[DataRequired()])
    customer_description = TextAreaField(u'Customer description', validators=[DataRequired()])
    customer_sla = TextAreaField(u'Customer SLAs', validators=[DataRequired()])


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class AddAssetForm(FlaskForm):
    asset_name = StringField(u'Asset name', validators=[DataRequired()])
    asset_description = StringField(u'Asset description', validators=[DataRequired()])
    asset_icon_compromised = StringField(u'Asset icon compromised name', default="ioc_question-mark.png")
    asset_icon_not_compromised = StringField(u'Asset icon not compromised name', default="question-mark.png")


class AttributeForm(FlaskForm):
    attribute_content = TextAreaField(u'Attribute content', validators=[DataRequired()])


class AddIocTypeForm(FlaskForm):
    type_name = StringField(u'Type name', validators=[DataRequired()])
    type_description = StringField(u'Type description', validators=[DataRequired()])
    type_taxonomy = TextAreaField(u'Type taxonomy')
    type_validation_regex = StringField(u'Type validation regex')
    type_validation_expect = StringField(u'Type validation expectation')


class CaseClassificationForm(FlaskForm):
    name = StringField(u'Case classification name', validators=[DataRequired()])
    name_expanded = StringField(u'Case classification name expanded', validators=[DataRequired()])
    description = StringField(u'Case classification description', validators=[DataRequired()])


class EvidenceTypeForm(FlaskForm):
    name = StringField(u'Evidence type name', validators=[DataRequired()])
    description = StringField(u'Evidence type description', validators=[DataRequired()])


class CaseStateForm(FlaskForm):
    state_name = StringField(u'Case state name', validators=[DataRequired()])
    state_description = StringField(u'Case state description', validators=[DataRequired()])


class AddReportTemplateForm(FlaskForm):
    report_name = StringField(u'Report name', validators=[DataRequired()])
    report_description = StringField(u'Report description', validators=[DataRequired()])
    report_name_format = StringField(u'Report name formating', validators=[DataRequired()])
    report_language = SelectField(u'Language', validators=[DataRequired()])
    report_type = SelectField(u'Report Type', validators=[DataRequired()])


class CaseTemplateForm(FlaskForm):
    case_template_json = TextAreaField(u'Case Template JSON', validators=[DataRequired()])


class AddUserForm(FlaskForm):
    user_login = StringField(u'Name', validators=[DataRequired()])
    user_name = StringField(u'Username', validators=[DataRequired()])
    user_password = PasswordField(u'Password', validators=[DataRequired()])
    user_email = StringField(u'Email', validators=[DataRequired(), Email()])
    user_is_service_account = BooleanField(u'Use as service account')


class AddGroupForm(FlaskForm):
    group_name = StringField(u'Group name', validators=[DataRequired()])
    group_description = StringField(u'Group description', validators=[DataRequired()])


class AddOrganisationForm(FlaskForm):
    org_name = StringField(u'Organisation name', validators=[DataRequired()])
    org_description = StringField(u'Organisation description', validators=[DataRequired()])
    org_url = StringField(u'Organisation url', validators=[DataRequired()])
    org_logo = StringField(u'Organisation logo', validators=[DataRequired()])
    org_email = StringField(u'Organisation email', validators=[DataRequired()])
    org_nationality = StringField(u'Organisation nationality', validators=[DataRequired()])
    org_sector = StringField(u'Organisation nationality', validators=[DataRequired()])
    org_type = StringField(u'Organisation type', validators=[DataRequired()])


class ModalAddCaseAssetForm(FlaskForm):
    asset_id = SelectField(u'Asset type', validators=[DataRequired()])


class AddCaseForm(FlaskForm):
    case_name = StringField(u'Case name', validators=[InputRequired()])
    case_description = StringField(u'Case description', validators=[InputRequired()])
    case_soc_id = StringField(u'SOC Ticket')
    case_customer = SelectField(u'Customer', validators=[InputRequired()])
    case_organisations = SelectMultipleField(u'Organisations')
    classification_id = SelectField(u'Classification')
    case_template_id = SelectField(u'Case Template')


class ContactForm(FlaskForm):
    contact_name = StringField(u'Contact name', validators=[DataRequired()])
    contact_role = StringField(u'Contact role', validators=[DataRequired()])
    contact_email = StringField(u'Contact email', validators=[DataRequired(), Email()])
    contact_work_phone = StringField(u'Work phone', validators=[DataRequired()])
    contact_mobile_phone = StringField(u'Mobile phone', validators=[DataRequired()])
    contact_note = TextAreaField(u'Contact description', validators=[DataRequired()])


class PipelinesCaseForm(FlaskForm):
    pipeline = SelectField(u'Processing pipeline')


class AssetBasicForm(FlaskForm):
    asset_name = StringField(u'Name', validators=[DataRequired()])
    asset_description = TextAreaField(u'Description')
    asset_domain = StringField(u'Domain')
    asset_ip = StringField(u'Domain')
    asset_info = TextAreaField(u'Asset Info')
    asset_compromise_status_id = SelectField(u'Compromise Status')
    asset_type_id = SelectField(u'Asset Type', validators=[DataRequired()])
    analysis_status_id = SelectField(u'Analysis Status', validators=[DataRequired()])
    asset_tags = StringField(u'Asset Tags')


class CaseEventForm(FlaskForm):
    event_title = StringField(u'Event Title', validators=[DataRequired()])
    event_source = StringField(u'Event Source')
    event_content = TextAreaField(u'Event Description')
    event_raw = TextAreaField(u'Event Raw data')
    event_assets = SelectField(u'Event Asset')
    event_category_id = SelectField(u'Event Category')
    event_tz = StringField(u'Event Timezone', validators=[DataRequired()])
    event_in_summary = BooleanField(u'Add to summary')
    event_tags = StringField(u'Event Tags')
    event_in_graph = BooleanField(u'Display in graph')


class CaseTaskForm(FlaskForm):
    task_title = StringField(u'Task Title', validators=[DataRequired()])
    task_description = TextAreaField(u'Task description')
    task_status_id = SelectField(u'Task status', validators=[DataRequired()])
    task_assignees_id = SelectMultipleField(u'Assignee(s)')
    task_tags = StringField(u'Task Tags')


class CaseGlobalTaskForm(FlaskForm):
    task_title = StringField(u'Task Title')
    task_description = TextAreaField(u'Task description')
    task_assignee_id = SelectField(u'Task assignee')
    task_status_id = SelectField(u'Task status')
    task_tags = StringField(u'Task Tags')


class ModalAddCaseIOCForm(FlaskForm):
    ioc_tags = StringField(u'IOC Tags')
    ioc_value = TextAreaField(u'IOC Value', validators=[DataRequired()])
    ioc_description = TextAreaField(u'IOC Description')
    ioc_type_id = SelectField(u'IOC Type', validators=[DataRequired()])
    ioc_tlp_id = SelectField(u'IOC TLP', validators=[DataRequired()])


class ModalDSFileForm(FlaskForm):
    file_original_name = StringField(u'Filename', validators=[DataRequired()])
    file_description = TextAreaField(u'file_description')
    file_password = StringField(u'File password')
    file_is_ioc = BooleanField(u'File is IOC')
    file_is_evidence = BooleanField(u'File is Evidence')


class CaseNoteForm(FlaskForm):
    note_title = StringField(u'Note title', validators=[DataRequired()])
    note_content = StringField(u'Note content')


class AddModuleForm(FlaskForm):
    module_name = StringField(u'Module name', validators=[DataRequired()])


class UpdateModuleParameterForm(FlaskForm):
    module_name = StringField(u'Module name', validators=[DataRequired()])
