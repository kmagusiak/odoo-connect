import base64
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional, Union, cast

from .odoo_rpc import OdooModel

__doc__ = """Formatting of fields for Odoo."""

NOT_FORMATTED_FIELDS = {
    'display_name',
    'write_date',
    'create_date',
    'write_uid',
    'create_uid',
    '__last_update',
}

"""Default formatters for models"""
DEFAULT_FORMATTERS: Dict[OdooModel, "Formatter"] = {}


def decode_default(value) -> Any:
    """Decode a value from Odoo (identity function)"""
    return value


def decode_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def decode_date(value) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def decode_binary(value) -> bytes:
    """Decode bytes from a base64"""
    if not value:
        return b''
    return base64.b64decode(value)


def format_default(v: Any):
    """Format a value for Odoo"""
    if isinstance(v, str):
        v = v.strip()
    return v or False


def format_datetime(v: Union[datetime, date, str]):
    """Format a datetime to insert into Odoo"""
    if isinstance(v, datetime):
        # format ISO with a space an ignore millisenconds
        return v.isoformat(sep=" ", timespec='seconds')
    if isinstance(v, str):
        return v.strip()[:19] or False
    if isinstance(v, date):
        return v.isoformat() + " 00:00:00"
    return False


def format_date(v: Union[datetime, date, str]):
    """Format a date to insert into Odoo"""
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip()[:10] or False
    return False


def format_binary(v: Union[bytes, str]) -> str:
    """Format bytes to insert into Odoo (as base64)"""
    if isinstance(v, str):
        v = bytes(v, 'utf-8')
    encoded = base64.b64encode(v)
    return str(encoded, 'ascii')


class Formatter:
    """Format fields into a format expected by Odoo."""

    """Transformations to apply to source fields.
    Use an empty string to mask some of them."""
    field_map: Dict[str, str]
    format_function: Dict[str, Callable[[Any], Any]]
    decode_function: Dict[str, Callable[[Any], Any]]

    def __init__(self, model: OdooModel = None, *, lower_case_fields: bool = False):
        """New formatter

        :param model: The model for which the formatter is generated (initializes formatters)
        :param lower_case_fields: Whether to transform source fields into lower-case
        """
        self.format_function = defaultdict(lambda: format_default)
        self.decode_function = defaultdict(lambda: decode_default)
        self.model = model
        self.lower_case_fields = lower_case_fields
        self.field_map = {}
        if not model:
            return
        # set the formats from the model
        functions = {
            'datetime': (format_datetime, decode_datetime),
            'date': (format_date, decode_date),
            'binary': (format_binary, decode_binary),
            'image': (format_binary, decode_binary),
        }
        for field, info in model.fields().items():
            formatter, decoder = functions.get(
                cast(str, info.get('type')), (format_default, decode_default)
            )
            if formatter is not format_default:
                self.format_function.setdefault(field, formatter)
            if decoder is not decode_default:
                self.decode_function.setdefault(field, decoder)

    def map_field_name(self, name: str) -> str:
        """Transform a source field name into model's name"""
        name = self.field_map.get(name, name)
        if self.lower_case_fields:
            name = name.lower()
        return name

    def format_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Apply formatting to each field"""
        d_renamed = [(self.map_field_name(f), v) for f, v in d.items()]
        return {
            f: self.format_function[f](v)
            for f, v in d_renamed
            if f and f not in NOT_FORMATTED_FIELDS
        }

    def decode_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Apply decoding to each field"""
        return {f: self.decode_function[f](v) for f, v in d.items()}


def get_default_formatter(model: OdooModel) -> Formatter:
    """Get the default dict formatter function"""
    formatter = DEFAULT_FORMATTERS.get(model)
    if not formatter:
        DEFAULT_FORMATTERS[model] = formatter = Formatter(model)
    return formatter
