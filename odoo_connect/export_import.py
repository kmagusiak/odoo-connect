import base64
import json
from typing import Dict, List, Union, overload

from .odoo_rpc_base import OdooClientBase, OdooModel

encode_bytes = base64.b64encode
decode_bytes = base64.b64decode


#######################################
# ATTACHMENTS


@overload
def get_attachment(model: OdooModel, attachment_id: int) -> bytes:
    ...


@overload
def get_attachment(model: OdooModel, encoded_value: str) -> bytes:
    ...


@overload
def get_attachment(model: OdooModel, id: int, field_name: str) -> bytes:
    ...


def get_attachment(model, value_or_id, field_name=None) -> bytes:
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
    return get_attachments(model.odoo, [value_or_id])[0]


def get_attachments(odoo: OdooClientBase, ids: List[int]) -> List[bytes]:
    data = odoo['ir.attachment'].read(ids, ['datas'])
    return [decode_bytes(r['datas']) for r in data]


#######################################
# REPORTS


def get_reports(model: OdooModel):
    return model.odoo['ir.actions.report'].search_read(
        [('model', '=', model.model)], ['name', 'report_type', 'report_name']
    )


def get_report(model: OdooModel, reportname: str, id: int, converter='pdf') -> bytes:
    from .odoo_rpc_json import OdooClientJSON, urljoin

    if not isinstance(model.odoo, OdooClientJSON):
        raise RuntimeError('Can get the report only using OdooClientJSON')

    url = urljoin(model.odoo.url, f"/report/{converter}/{reportname}/{id}")
    req = model.odoo.session.get(url)
    req.raise_for_status()
    return req.content


#######################################
# IMPORT AND EXPORT


def load(model: OdooModel, fields: List[str], data: List[Dict]):
    """Load the data into the model"""
    return model.execute("load", fields=fields, data=data)


def export(
    model: OdooModel,
    filter_or_domain: Union[str, List],
    export_or_fields: Union[str, List[str]],
    with_header: bool = True,
    expand_many: bool = True,
) -> List[List]:
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


def flatten(data, fields, expand_many=False):
    if isinstance(data, list):
        return [flatten(d, fields, expand_many=expand_many) for d in data]
    if not isinstance(data, dict):
        return data
    # TODO
    return data
