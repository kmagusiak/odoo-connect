import base64
import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Tuple, Union, overload

from .odoo_rpc_base import OdooClientBase, OdooModel, urljoin

__doc__ = """
Export and import data from Odoo.

## Data
To download values, use `export_data` which will return a table-like structure.
To import, you can use `load_data` to upload data into Odoo.
Alternatively, you can use the formatter to prepare data for upload and
then call create or write methods.

## Attachments
Get attachments and read binary values.

## Reports
Generate a report.
"""

NOT_FORMATTED_FIELDS = {
    'display_name',
    'write_date',
    'create_date',
    'write_uid',
    'create_uid',
    '__last_update',
}

#######################################
# ATTACHMENTS


@overload
def get_attachment(model: OdooModel, attachment_id: int) -> bytes:
    """Get attachment by ID"""
    ...


@overload
def get_attachment(model: OdooModel, encoded_value: str) -> bytes:
    """Get attachment from base64 encoded value"""
    ...


@overload
def get_attachment(model: OdooModel, id: int, field_name: str) -> bytes:
    """Get attachment from a field in an object by id"""
    ...


def get_attachment(model, value_or_id, field_name=None) -> bytes:
    if not value_or_id:
        return b''
    # we have a value, decode it
    if not isinstance(value_or_id, int):
        if field_name is not None:
            raise ValueError("Unexpected argument field_name because we don't have an id")
        return decode_bytes(value_or_id)
    # if we have a field name, decode the value or get the ID
    if field_name:
        field_info = model.fields().get(field_name, {})
        record = model.read(value_or_id, [field_name])
        value = record[0][field_name]
        if field_info.get("relation") == "ir.attachment":
            if field_info.get("type") != "many2one":
                raise RuntimeError(
                    "Field %s is not a many2one, here are the values: %s" % (field_name, value)
                )
            value = value[0]
        elif field_info.get("type") != "binary":
            raise RuntimeError("%s is neither a binary or an ir.attachment field" % field_name)
        return get_attachment(model, value)
    # read the attachment
    return get_attachments(model.odoo, [value_or_id])[0][1]


def decode_bytes(value) -> bytes:
    return base64.b64decode(value)


def get_attachments(odoo: OdooClientBase, ids: List[int]) -> List[Tuple[str, bytes]]:
    """Get a list of tuples (name, raw_bytes) from ir.attachment by ids

    :param odoo: Odoo client
    :param ids: List of ids of attachments
    :return: List of tuples (name, raw_bytes)
    """
    data = odoo['ir.attachment'].read(ids, ['name', 'datas'])
    return [(r['name'], decode_bytes(r['datas'])) for r in data]


#######################################
# REPORTS


def get_reports(model: OdooModel) -> List[Dict]:
    """Get a list of reports from a model"""
    return model.odoo['ir.actions.report'].search_read(
        [('model', '=', model.model)], ['name', 'report_type', 'report_name']
    )


def get_report(model: OdooModel, report_name: str, id: int, converter='pdf') -> bytes:
    """Generate and download a report

    :param model: Odoo model
    :param reportname: The name of the report
    :param id: The id of the object
    :param converter: The output type (default: pdf)
    :return: Bytes of the report
    """
    from .odoo_rpc_json import OdooClientJSON, urljoin

    # We need to use the session, because there is no public API since v14 to
    # render a report and get the bytes.
    # In the implementation, the session is authenticated.
    if not isinstance(model.odoo, OdooClientJSON):
        raise RuntimeError('Can get the report only using OdooClientJSON')

    if converter.startswith('qweb-'):
        converter = converter[5:]
    url = urljoin(model.odoo.url, f"/report/{converter}/{report_name}/{id}")
    req = model.odoo.session.get(url)
    req.raise_for_status()
    return req.content


#######################################
# IMPORT AND EXPORT


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
    return str(encoded, 'ascii') or False


@overload
def get_formatter(type_name: str) -> Callable:
    ...


@overload
def get_formatter(model: OdooModel) -> defaultdict:  # [str, Callable]:
    ...


def get_formatter(model_or_type):
    """Get a default formatter for fields in a model"""
    # Get a formatter for a model
    if isinstance(model_or_type, OdooModel):
        format = defaultdict(format_default)
        for field, info in model_or_type.fields().items():
            formatter = get_formatter(info.get('type'))
            if formatter is not format_default:
                format.setdefault(field, formatter)
        return format
    # Get for a type
    type_name = model_or_type
    if type_name == 'datetime':
        return format_datetime
    elif type_name == 'date':
        return format_date
    elif type_name == 'binary':
        return format_binary
    return format_default


def format_dict(data: Dict, formatter: defaultdict):
    """Applies formatting to each field"""
    return {f: formatter[f](v) for f, v in data.items() if f not in NOT_FORMATTED_FIELDS}


def load_data(model: OdooModel, fields: List[str], data: Iterable[List[List]]):
    """Load the data into the model"""
    # TODO handle insert and update
    # TODO handle batch uploads
    fields = [f.replace('.', '/') for f in fields]
    for data_part in data:
        yield model.execute("load", fields=fields, data=data_part)


def export_data(
    model: OdooModel,
    filter_or_domain: Union[str, List],
    export_or_fields: Union[str, List[str]],
    with_header: bool = True,
    expand_many: bool = False,
) -> List[List]:
    """Export data into a tabular format

    :param model: Odoo model
    :param filter_or_domain: Either a domain or an ir.filer name
    :param export_or_fields: Either a list of fields (like is search_read_dict)
        or an ir.exports name
    :param with_header: Include the header in the result (default: True)
    :param expand_many: Flatten lists embedded in the result (default: False)
    :return: List of rows with data
    """
    odoo = model.odoo
    kwargs = {}

    if isinstance(filter_or_domain, str):
        filter_data = odoo['ir.filters'].search_read_dict(
            [
                ('name', '=', filter_or_domain),
                ('model_id', '=', model.model),
            ],
            ['domain', 'context', 'sort'],
        )
        if not filter_data:
            raise ValueError('Filter not found')
        domain = filter_data.get('domain')
        if filter_data.get('sort'):
            kwargs['order'] = json.loads(filter_data.get('sort'))
        if filter_data.get('context'):
            kwargs['context'] = json.loads(filter_data.get('context'))
    else:
        domain = filter_or_domain

    if isinstance(export_or_fields, str):
        fields = odoo['ir.exports.line'].search_read(
            [
                ('export_id.name', '=', export_or_fields),
                ('export_id.resource', '=', model.model),
            ],
            ['name'],
        )
        fields = [f['name'].replace('/', '.') for f in fields]
    else:
        fields = export_or_fields
    if not fields:
        raise ValueError('No fields to export')

    records = model.search_read_dict(domain, fields)

    data = flatten(records, fields, expand_many=expand_many)
    if with_header:
        data.insert(0, [str(f) for f in fields])
    return data


def add_url(model: OdooModel, data: List, *, model_id_func=None, url_field='url'):
    """Add an URL field to data

    :param model: The model
    :param data: The list of dicts or rows (list to append to)
    :param model_id_func: The function to get a tuple (model_name, id)
    :param url_field: The name of the URL field for dicts (default: url)
    """
    base_url = model.odoo.url
    if not model_id_func and data:
        if isinstance(data[0], list):
            model_id_func = lambda r: (model.model, r[0])  # noqa: E731
        else:
            model_id_func = lambda d: (model.model, d['id'])  # noqa: E731
    for row in data:
        model_name, id = model_id_func(row)
        url = f"/web#model={model_name}&id={id}"
        if isinstance(row, dict):
            row[url_field] = urljoin(base_url, url.format(id=id))
        elif isinstance(row, list):
            row.append(urljoin(base_url, url.format(id=id)))
        else:
            raise TypeError('Cannot append the url to %s' % type(row))


@overload
def _flatten(value: List, field_levels: List[str]) -> List:
    ...


@overload
def _flatten(value: Dict, field_levels: List[str]) -> Union[Any, bool]:
    ...


@overload
def _flatten(value: Any, field_levels: List[str]) -> Any:
    ...


def _flatten(value, field_levels: List[str]) -> Any:
    if not field_levels:
        return value
    if isinstance(value, list):
        return [_flatten(i, field_levels) for i in value]
    if isinstance(value, dict):
        return _flatten(value.get(field_levels[0]), field_levels[1:])
    return False  # default


def _expand_many(data: List[Dict]) -> List[Dict]:
    for d in data:
        should_yield = True
        for k, v in d.items():
            if isinstance(v, list) and len(v):
                should_yield = False
                for i in v:
                    yield from _expand_many([{**d, k: i}])
        for k, v in d.items():
            if should_yield and isinstance(v, dict):
                should_yield = False
                for row in _expand_many([v]):
                    yield {**d, k: row}
        if should_yield:
            yield d


def flatten(data: List[Dict], fields: List[str], expand_many=False) -> List[List]:
    """Flatten each dict with values into a single row"""
    if expand_many:
        data = list(_expand_many(data))
    field_levels = [f.split('.') for f in fields]
    return [[_flatten(d.get(fl[0]), fl[1:]) for fl in field_levels] for d in data]


__all__ = [
    'get_attachment',
    'get_attachments',
    'get_report',
    'get_reports',
    'get_formatter',
    'format_dict',
    'load_data',
    'export_data',
    'add_url',
]
