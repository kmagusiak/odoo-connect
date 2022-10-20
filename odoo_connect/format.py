import base64
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Union, cast

from .odoo_rpc import OdooModel

__doc__ = """
Formatting of fields for Odoo.
"""

NOT_FORMATTED_FIELDS = {
    'display_name',
    'write_date',
    'create_date',
    'write_uid',
    'create_uid',
    '__last_update',
}


def format_default(v: Any):
    """Format a value for Odoo"""
    if isinstance(v, str):
        v = v.strip()
    return v or False


def format_datetime(v: Union[datetime, str]):
    """Format a datetime to insert into Odoo"""
    if isinstance(v, datetime):
        # format ISO with a space an ignore millisenconds
        return v.isoformat(sep=" ", timespec='seconds')
    if isinstance(v, str):
        return v.strip()[:19] or False
    return False


def format_date(v: Union[datetime, date, str]):
    """Format a date to insert into Odoo"""
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip()[:10] or False
    return v


def format_binary(v: Union[bytes, str]) -> str:
    """Format bytes to insert into Odoo (as base64)"""
    if isinstance(v, str):
        v = bytes(v, 'utf-8')
    encoded = base64.b64encode(v)
    return str(encoded, 'ascii')


class Formatter(defaultdict):
    """Format fields into a format expected by Odoo."""

    """Transformations to apply to source fields.
    Use an empty string to mask some of them."""
    field_map: Dict[str, str]

    def __init__(self, model: OdooModel = None, *, lower_case_fields: bool = False):
        """New formatter

        :param model: The model for which the formatter is generated (initializes formatters)
        :param lower_case_fields: Whether to transform source fields into lower-case
        """
        super().__init__(lambda: format_default)
        self.model = model
        self.lower_case_fields = lower_case_fields
        self.field_map = {}

        # set the formats from the model
        if model:
            formatters = {
                'datetime': format_datetime,
                'date': format_date,
                'binary': format_binary,
                'image': format_binary,
            }
            for field, info in model.fields().items():
                formatter = formatters.get(cast(str, info.get('type')), format_default)
                if formatter is not format_default:
                    self.setdefault(field, formatter)

    def map_field(self, name):
        """Transform a source field name into model's name"""
        name = self.field_map.get(name, name)
        if self.lower_case_fields:
            name = name.lower()
        return name

    def format_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Apply formatting to each field"""
        d_renamed = [(self.map_field(f), v) for f, v in d.items()]
        return {f: self[f](v) for f, v in d_renamed if f and f not in NOT_FORMATTED_FIELDS}
