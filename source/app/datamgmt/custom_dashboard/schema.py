from marshmallow import Schema, fields as ma_fields, validate, validates_schema, ValidationError


class DashboardFilterSchema(Schema):
    table = ma_fields.String(required=True)
    column = ma_fields.String(required=True)
    operator = ma_fields.String(required=True, validate=validate.OneOf(['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'nin', 'between', 'contains']))
    value = ma_fields.Raw(required=True)


class DashboardWidgetFieldSchema(Schema):
    table = ma_fields.String(required=True)
    column = ma_fields.String(required=True)
    aggregation = ma_fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(['count', 'sum', 'avg', 'min', 'max', 'ratio'])
    )
    alias = ma_fields.String(required=False, allow_none=True)
    filter = ma_fields.Nested(DashboardFilterSchema, required=False)


class DashboardWidgetSchema(Schema):
    name = ma_fields.String(required=True)
    chart_type = ma_fields.String(
        required=True,
        validate=validate.OneOf(['line', 'bar', 'pie', 'number', 'percentage', 'table', 'timechart'])
    )
    fields = ma_fields.List(ma_fields.Nested(DashboardWidgetFieldSchema), required=True, validate=validate.Length(min=1))
    filters = ma_fields.List(ma_fields.Nested(DashboardFilterSchema), required=False)
    group_by = ma_fields.List(ma_fields.String(), required=False)
    time_bucket = ma_fields.String(required=False, allow_none=True)
    options = ma_fields.Dict(required=False)
    layout = ma_fields.Dict(required=False)


class DashboardSectionSchema(Schema):
    id = ma_fields.String(required=False)
    title = ma_fields.String(required=False, allow_none=True)
    description = ma_fields.String(required=False, allow_none=True)
    show_divider = ma_fields.Boolean(required=False)
    widgets = ma_fields.List(ma_fields.Nested(DashboardWidgetSchema), required=True, validate=validate.Length(min=1))


class CustomDashboardSchema(Schema):
    name = ma_fields.String(required=True)
    description = ma_fields.String(allow_none=True)
    is_shared = ma_fields.Boolean(required=False)
    widgets = ma_fields.List(ma_fields.Nested(DashboardWidgetSchema), required=False)
    sections = ma_fields.List(ma_fields.Nested(DashboardSectionSchema), required=False)

    @validates_schema
    def validate_widget_structure(self, data, **kwargs):
        widgets = data.get('widgets') or []
        sections = data.get('sections') or []

        section_widget_count = sum(len(section.get('widgets') or []) for section in sections)
        total_widgets = len(widgets) + section_widget_count

        if total_widgets <= 0:
            raise ValidationError('At least one widget must be defined.', field_name='widgets')
