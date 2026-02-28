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

import logging as log
import os
import re
from datetime import datetime

from app.models.errors import BusinessProcessingError
from app.blueprints.iris_user import iris_current_user
from docx_generator.docx_generator import DocxGenerator
from docx_generator.adapters.docx.docx_adapter import make_run, make_table_row, make_table_cell, make_paragraph
from docx_generator.adapters.docx.style_adapter import RenderStylesCollection
from docx_generator.adapters.docx.style_adapter import DocxStyleAdapter
from docx_generator.adapters.mistletoe.DocxRenderer import DocxRenderer
from docx_generator.exceptions import rendering_error
from jinja2 import Environment
from markupsafe import Markup

from app import app
from app.business.cases import cases_export_to_json

from app.datamgmt.activities.activities_db import get_auto_activities
from app.datamgmt.activities.activities_db import get_manual_activities
from app.iris_engine.utils.tracker import track_activity

from app.models.models import CaseTemplateReport

from app.business.reports.ImageHandler import ImageHandler
from app.iris_engine.utils.common import IrisJinjaEnv

LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
log.basicConfig(level=log.INFO, format=LOG_FORMAT)


def _get_docid():
    return '{}'.format(datetime.utcnow().strftime('%y%m%d_%H%M'))


def _get_case_info(case_identifier):
    case_info = cases_export_to_json(case_identifier)

    # Get customer, user and case title
    case_info['doc_id'] = _get_docid()
    case_info['user'] = iris_current_user.name

    # Set date
    case_info['date'] = datetime.utcnow().strftime("%Y-%m-%d")
    customer_name = case_info['case'].get('client').get('customer_name')
    case_info['case']['for_customer'] = f'{customer_name} (legacy::use client.customer_name)'

    return case_info


def _get_activity_info(case_identifier):
    auto_activities = get_auto_activities(case_identifier)
    manual_activities = get_manual_activities(case_identifier)
    case_info_in = _get_case_info(case_identifier)

    doc_id = _get_docid()

    case_info = {
        'auto_activities': auto_activities,
        'manual_activities': manual_activities,
        'date': datetime.utcnow(),
        'gen_user': iris_current_user.name,
        'case': {'name': case_info_in['case'].get('name'),
                 'open_date': case_info_in['case'].get('open_date'),
                 'for_customer': case_info_in['case'].get('for_customer'),
                 'client': case_info_in['case'].get('client')
                 },
        'doc_id': doc_id
    }

    return case_info


def _get_case_info_according_to_type(case_identifier, doc_type):
    """Returns case information

    Args:
        doc_type (_type_): Investigation or Activities report

    Returns:
        _type_: case info
    """
    if doc_type == 'Investigation':
        return _get_case_info(case_identifier)
    if doc_type == 'Activities':
        return _get_activity_info(case_identifier)

    return None


class IrisDocxGenerator(DocxGenerator):
    _MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')
    _MARKDOWN_CODE_FENCE_RE = re.compile(r'^\s*(`{3,}|~{3,}).*$')
    _MARKDOWN_HEADING_RE = re.compile(r'^\s{0,3}(#{1,6})\s+(.*)$')
    _RENDERER_STYLE_FIELDS = (
        'header1', 'header2', 'header3', 'header4', 'header5', 'header6',
        'ul', 'ol', 'paragraph', 'inline_code', 'code', 'quote',
        'hyperlink', 'image_caption', 'strong', 'italic', 'strike', 'table'
    )
    _DOCX_TABLE_INJECTION_PREFIX = '</w:t></w:r></w:p>'
    _DOCX_TABLE_INJECTION_SUFFIX = '<w:p><w:r><w:t xml:space="preserve">'

    @staticmethod
    def _builtin_heading_paragraph_style(level: int) -> str:
        """Fallback paragraph style when template render styles don't define headerN."""
        safe_level = min(max(int(level), 1), 6)
        return f'<w:pPr><w:pStyle w:val="Heading{safe_level}"/></w:pPr>'

    @classmethod
    def _is_markdown_table_separator(cls, line: str) -> bool:
        return bool(cls._MARKDOWN_TABLE_SEPARATOR_RE.match(line or ''))

    @staticmethod
    def _split_markdown_table_row(row: str):
        row = row.strip()
        if row.startswith('|'):
            row = row[1:]
        if row.endswith('|'):
            row = row[:-1]
        return [cell.strip() for cell in row.split('|')]

    @classmethod
    def _split_markdown_and_tables(cls, markdown_string: str):
        segments = []
        current_markdown = []
        lines = markdown_string.splitlines()
        idx = 0

        while idx < len(lines):
            current_line = lines[idx]
            code_fence_match = cls._MARKDOWN_CODE_FENCE_RE.match(current_line)
            if code_fence_match:
                if current_markdown:
                    segments.append(('markdown', '\n'.join(current_markdown)))
                    current_markdown = []

                fence_token = code_fence_match.group(1)
                fence_char = fence_token[0]
                fence_len = len(fence_token)

                idx += 1
                code_lines = []
                closing_fence_re = re.compile(r'^\s*' + re.escape(fence_char) + '{' + str(fence_len) + r',}\s*$')
                while idx < len(lines):
                    fence_candidate = lines[idx]
                    if closing_fence_re.match(fence_candidate):
                        idx += 1
                        break
                    code_lines.append(fence_candidate)
                    idx += 1

                segments.append(('code', code_lines))
                continue

            next_line = lines[idx + 1] if idx + 1 < len(lines) else None
            is_table_start = (
                next_line is not None
                and '|' in current_line
                and cls._is_markdown_table_separator(next_line)
            )

            if not is_table_start:
                current_markdown.append(current_line)
                idx += 1
                continue

            if current_markdown:
                segments.append(('markdown', '\n'.join(current_markdown)))
                current_markdown = []

            table_lines = [current_line, next_line]
            idx += 2
            while idx < len(lines):
                table_row = lines[idx]
                if not table_row.strip() or '|' not in table_row:
                    break
                following_line = lines[idx + 1] if idx + 1 < len(lines) else None
                starts_new_table = (
                    following_line is not None
                    and '|' in table_row
                    and cls._is_markdown_table_separator(following_line)
                )
                if starts_new_table:
                    break
                table_lines.append(table_row)
                idx += 1

            segments.append(('table', table_lines))

        if current_markdown:
            segments.append(('markdown', '\n'.join(current_markdown)))

        return segments

    @staticmethod
    def _render_markdown_table(table_lines, style: DocxStyleAdapter = None):
        header_cells = IrisDocxGenerator._split_markdown_table_row(table_lines[0])
        body_rows = [
            IrisDocxGenerator._split_markdown_table_row(row)
            for row in table_lines[2:]
        ]
        paragraph_style = getattr(style, 'paragraph', '') or ''
        table_style = getattr(style, 'table', '') or ''

        row_widths = [len(header_cells)] + [len(row) for row in body_rows]
        column_count = max(max(row_widths), 1)
        column_width = max(1, 9016 // column_count)
        tbl_grid = '<w:tblGrid>{}</w:tblGrid>'.format(
            ''.join(f'<w:gridCol w:w="{column_width}"/>' for _ in range(column_count))
        )

        def render_row(cells):
            normalized_cells = cells + [''] * (column_count - len(cells))
            row_xml = ''.join(
                make_table_cell(paragraph_style, make_run('', cell))
                for cell in normalized_cells
            )
            return make_table_row(row_xml)

        header_xml = render_row(header_cells)
        body_rows_xml = ''.join(render_row(row_cells) for row_cells in body_rows)

        return '<w:tbl>{}{}{}</w:tbl>'.format(table_style, tbl_grid, header_xml + body_rows_xml)

    @staticmethod
    def _render_markdown_code_block(code_lines, style: DocxStyleAdapter = None):
        code_paragraph_style = getattr(style, 'code', '') or ''
        paragraph_style = code_paragraph_style or getattr(style, 'paragraph', '') or ''
        run_style = '' if code_paragraph_style else (getattr(style, 'inline_code', '') or '')
        code_text = '\n'.join(code_lines) if code_lines else ''
        return make_paragraph(paragraph_style, make_run(run_style, code_text))

    @staticmethod
    def _markdown_to_styled_lines(markdown_segment: str, style: DocxStyleAdapter = None):
        lines = []
        for raw_line in (markdown_segment or '').splitlines():
            if not raw_line.strip():
                continue

            heading_match = IrisDocxGenerator._MARKDOWN_HEADING_RE.match(raw_line)
            if heading_match:
                level = min(len(heading_match.group(1)), 6)
                text = heading_match.group(2).strip()
                paragraph_style = getattr(style, f'header{level}', '') or ''
                if not paragraph_style:
                    paragraph_style = IrisDocxGenerator._builtin_heading_paragraph_style(level)
            else:
                text = raw_line
                text = re.sub(r'^\s*[-+*]\s+', '', text)
                text = re.sub(r'^\s*\d+\.\s+', '', text)
                paragraph_style = getattr(style, 'paragraph', '') or ''

            # Strip common inline formatting markers while keeping content.
            text = text.replace('**', '').replace('__', '')
            text = text.replace('*', '').replace('_', '')
            text = text.replace('`', '')
            text = text.strip()
            if not text:
                continue

            lines.append((text, paragraph_style))

        return lines

    @staticmethod
    def _safe_style_value(value):
        if value is None:
            return ''
        return value if isinstance(value, str) else str(value)

    @classmethod
    def _normalize_style(cls, style, style_name='default'):
        normalized = {field: cls._safe_style_value(getattr(style, field, '')) for field in cls._RENDERER_STYLE_FIELDS}
        warnings = getattr(style, '_warnings', set()) if style is not None else set()
        style_name = getattr(style, 'name', None) or style_name or 'default'

        class _SafeStyle:
            def __init__(self, name, warnings_set, values):
                self.name = name
                self._warnings = set(warnings_set or set())
                for key, val in values.items():
                    setattr(self, key, val)

            def __getattr__(self, _):
                return ''

        return _SafeStyle(style_name, warnings, normalized)

    @staticmethod
    def _build_fallback_style(style_name='default'):
        """Provide a no-op style object so markdown rendering does not fail on missing template styles."""
        style_name = style_name or 'default'
        return IrisDocxGenerator._normalize_style(None, style_name)

    @staticmethod
    def _resolve_style(template_styles: RenderStylesCollection, renderer: DocxRenderer, style_name='default'):
        candidates = [style_name, 'normal', 'Normal']

        for candidate in candidates:
            try:
                style = template_styles.get_style(candidate)
                if style is not None:
                    return IrisDocxGenerator._normalize_style(style, candidate)
            except Exception:
                continue

        for attr in ('styles', '_styles'):
            styles = getattr(template_styles, attr, None)
            if isinstance(styles, dict) and styles:
                first_key = next(iter(styles.keys()))
                try:
                    style = template_styles.get_style(first_key)
                    if style is not None:
                        return IrisDocxGenerator._normalize_style(style, first_key)
                except Exception:
                    first_value = styles.get(first_key)
                    if first_value is not None:
                        return IrisDocxGenerator._normalize_style(first_value, first_key)

        for attr in ('style', '_style'):
            style = getattr(renderer, attr, None)
            if style is not None:
                return IrisDocxGenerator._normalize_style(style, style_name)

        return IrisDocxGenerator._build_fallback_style(style_name)

    @staticmethod
    def _markdown_to_styled_docx(markdown_string, renderer: DocxRenderer,
                                 template_styles: RenderStylesCollection, style_name='default'):
        """
        Render markdown in a way that stays valid when injected from a standard ``{{ ... }}`` DOCX run.
        Text blocks are rendered as visible paragraph text, and Markdown tables are injected as DOCX tables.
        """
        markdown_string = '' if markdown_string is None else str(markdown_string)
        style = IrisDocxGenerator._resolve_style(template_styles, renderer, style_name)
        if style is not None:
            renderer.set_style(style)
        segments = IrisDocxGenerator._split_markdown_and_tables(markdown_string)
        rendered_parts = []
        has_any_output = False

        for segment_type, payload in segments:
            if segment_type == 'table':
                if not has_any_output:
                    # Anchor one visible-safe character before closing tags so XML closers are kept.
                    rendered_parts.append(' ')
                    has_any_output = True
                rendered_parts.append(
                    '{}{}{}'.format(
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_PREFIX,
                        IrisDocxGenerator._render_markdown_table(payload, style),
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_SUFFIX
                    )
                )
                continue

            if segment_type == 'code':
                if not has_any_output:
                    rendered_parts.append(' ')
                    has_any_output = True
                rendered_parts.append(
                    '{}{}{}'.format(
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_PREFIX,
                        IrisDocxGenerator._render_markdown_code_block(payload, style),
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_SUFFIX
                    )
                )
                continue

            lines = IrisDocxGenerator._markdown_to_styled_lines(payload, style)
            for line, paragraph_style in lines:
                if not has_any_output:
                    rendered_parts.append(' ')
                    has_any_output = True
                rendered_parts.append(
                    '{}{}{}'.format(
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_PREFIX,
                        make_paragraph(paragraph_style, make_run('', line)),
                        IrisDocxGenerator._DOCX_TABLE_INJECTION_SUFFIX
                    )
                )

        return_value = ''.join(rendered_parts)
        return Markup(return_value)

    def _set_jinja2_custom_environment(self, base_path: str, template, jinja2_environment: Environment,
                                       renderer: DocxRenderer, template_styles: RenderStylesCollection) -> None:
        super()._set_jinja2_custom_environment(base_path, template, jinja2_environment, renderer, template_styles)

        # Override the upstream markdown filter so existing templates do not need
        # to be updated/republished to benefit from robust table rendering.
        def markdown(markdown_string, style_name='default'):
            return self._markdown_to_styled_docx(markdown_string, renderer, template_styles, style_name)

        jinja2_environment.filters['markdown'] = markdown

        # Backward-compatible alias introduced during #691 work.
        def markdown_styled(markdown_string, style_name='default'):
            return markdown(markdown_string, style_name)

        jinja2_environment.filters['markdown_styled'] = markdown_styled


class IrisMakeDocReport:
    """
    Generates a DOCX report for the case
    """

    def __init__(self, tmp_dir, report_id, caseid, safe_mode=False):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._caseid = caseid
        self._safe_mode = safe_mode

    def generate_doc_report(self, doc_type):
        case_info = _get_case_info_according_to_type(self._caseid, doc_type)
        if case_info is None:
            log.error('Unknown report type')
            track_activity('failed to generate report')
            raise BusinessProcessingError('Unknown report type')

        report = CaseTemplateReport.query.filter(CaseTemplateReport.id == self._report_id).first()

        name = f'{report.naming_format}.docx'
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

            generator = IrisDocxGenerator(image_handler=image_handler)
            generator.generate_docx("/",
                                    os.path.join(app.config['TEMPLATES_PATH'], report.internal_reference),
                                    case_info,
                                    output_file_path
                                    )

            return output_file_path

        except rendering_error.RenderingError as e:
            track_activity('failed to generate report')
            raise BusinessProcessingError('Failed to generate the report', e.__str__())


class IrisMakeMdReport:
    """
    Generates a MD report for the case
    """

    def __init__(self, tmp_dir, report_id, caseid, safe_mode=False):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._caseid = caseid
        self.safe_mode = safe_mode

    def generate_md_report(self, doc_type):
        case_info = _get_case_info_according_to_type(self._caseid, doc_type)
        if case_info is None:
            track_activity('failed to generate report')
            raise BusinessProcessingError('Unknown report type')

        # Get file extension
        report = CaseTemplateReport.query.filter(
            CaseTemplateReport.id == self._report_id).first()

        _, report_format = os.path.splitext(report.internal_reference)

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

            template_path = os.path.join(app.config['TEMPLATES_PATH'], report.internal_reference)
            with open(template_path, 'r', encoding="utf-8") as template_file:
                template = env.from_string(template_file.read())

            output_text = template.render(case_info)

            with open(output_file_path, 'w', encoding="utf-8") as html_file:
                html_file.write(output_text)

        except Exception as e:
            log.exception(f'Error while generating report: {e}')
            track_activity('failed to generate report')
            raise BusinessProcessingError('Failed to generate the report', e.__str__())

        return output_file_path
