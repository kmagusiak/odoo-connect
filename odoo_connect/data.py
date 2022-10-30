import json
import logging
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union, cast, overload

from .format import Formatter, decode_binary
from .odoo_rpc import OdooClient, OdooModel, urljoin

__doc__ = """Export and import data from Odoo.

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


#######################################
# ATTACHMENTS


@overload
def get_attachment(model: OdooModel, id: int) -> bytes:
    """Get attachment by ID"""
    ...


@overload
def get_attachment(model: OdooModel, *, encoded_value: str) -> bytes:
    """Get attachment from base64 encoded value"""
    ...


@overload
def get_attachment(model: OdooModel, id: int, field_name: str) -> bytes:
    """Get attachment from a field in an object by id"""
    ...


def get_attachment(
    model: OdooModel, id: int = 0, field_name: str = None, encoded_value: str = None
) -> bytes:
    if encoded_value is not None:
        return decode_binary(encoded_value)
    if not id:
        return b''
    # we read an attachment by id
    if not field_name:
        return get_attachments(model.odoo, [id])[id]
    # if we have a field name, decode the value or get the ID
    field_info = model.fields().get(field_name, {})
    record = model.read(id, [field_name])
    value = record[0][field_name]
    if field_info.get("relation") == "ir.attachment":
        if field_info.get("type") != "many2one":
            raise RuntimeError(
                "Field %s is not a many2one, here are the values: %s" % (field_name, value)
            )
        if not value:
            return b''
        value = value[0]
    elif field_info.get("type") != "binary":
        raise RuntimeError("%s is neither a binary or an ir.attachment field" % field_name)
    if isinstance(value, int):
        return get_attachment(model, value)
    return decode_binary(value)


def get_attachments(odoo: OdooClient, ids: List[int]) -> Dict[int, bytes]:
    """Get a list of tuples (name, raw_bytes) from ir.attachment by ids

    :param odoo: Odoo client
    :param ids: List of ids of attachments
    :return: Dict id -> raw_bytes
    """
    data = odoo['ir.attachment'].read(ids, ['datas'])
    return {r['id']: decode_binary(r['datas']) for r in data}


def list_attachments(
    model: OdooModel, ids: List[int], *, domain=[], fields=[], generate_access_token=False
) -> List[Dict]:
    """List attachments

    We search all attachments linked to the model and ids.
    All attachments, no matter if they have a res_field or not are read.
    We read the id, name, res_id, res_field.
    Special field names: public_url (generate public URL), datas (contents).

    :param model: The model
    :param ids: The record ids to filter on
    :param domain: Additional domain
    :param fields: Additional fields to read
    :param generate_access_token: Generate access token for the found documents
    :return: List of read properties from the attachments (id, name, res_field, ...)
    """
    url_field = None
    if 'public_url' in fields:
        url_field = 'public_url'
        fields += ['website_url', 'url', 'public', 'access_token']
    fields = list({'id', 'name', 'res_id', 'res_field', *fields} - {url_field})
    # Get the data
    if model.model == 'ir.attachment':
        attachments = model
        data = attachments.search_read(
            [
                ('id', 'in', ids),
            ]
            + domain,
            fields,
        )
    else:
        attachments = model.odoo['ir.attachment']
        data = attachments.search_read(
            [
                ('res_model', '=', model.model),
                ('res_id', 'in', ids),
                ('id', '!=', 0),  # to get all res_field
            ]
            + domain,
            fields,
        )
    # Get contents
    if 'datas' in fields:
        for d in data:
            d['datas'] = decode_binary(d['datas']) if d['datas'] else False
    # Generate access tokens
    if generate_access_token and data:
        tokens = attachments.execute('generate_access_token', [d['id'] for d in data])
        for d, token in zip(data, tokens):
            d['access_token'] = token
    # Compute a full url (false when not accessible)
    if url_field:

        def attachment_url(d, _model_name, _id):
            url = d.get('url') or d.get('website_url')
            if url and d.get('public'):
                return url
            if url and d.get('access_token'):
                url += ('&' if '?' in url else '?') + 'access_token=' + d.get('access_token')
                return url
            return False

        add_url(attachments, data, url_field=url_field, build_url=attachment_url)
    return data


def _download_content(
    odoo: OdooClient, url: str, *, params: Dict = {}, access_token: Optional[str] = None
) -> bytes:
    """Download contents from a URL"""
    # In the implementation, the session is authenticated.
    session = getattr(odoo, 'session', None)
    if not session:
        raise RuntimeError('Odoo client must have a session to download contents')

    url = urljoin(odoo.url, url)
    params = {}
    if access_token:
        params = {**params, 'access_token': access_token}
    req = session.get(url, params=params)
    req.raise_for_status()
    return req.content


def download_content(
    model: OdooModel,
    id: int,
    field_name: Optional[str] = None,
    *,
    access_token: Optional[str] = None,
) -> bytes:
    """Download contents from /web"""
    if field_name:
        url = f"/web/content/{model.model}/{id}/{field_name}"
    else:
        url = f"/web/content/{id}"
    return _download_content(model.odoo, url, access_token=access_token)


def download_image(
    model: OdooModel,
    id: int,
    field_name: Optional[str] = None,
    *,
    dimensions=None,
    access_token: Optional[str] = None,
):
    """Download an image from /web"""
    if field_name:
        url = f"/web/image/{model.model}/{id}/{field_name}"
    else:
        url = f"/web/image/{id}"
    if dimensions:
        url += "/%dx%d" % dimensions
    return _download_content(model.odoo, url, access_token=access_token)


#######################################
# REPORTS


def list_reports(model: OdooModel) -> List[Dict]:
    """List of reports from a model"""
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
    # We need to use the session, because there is no public API since v14 to
    # render a report and get the bytes.
    if converter.startswith('qweb-'):
        converter = converter[5:]
    url = f"/report/{converter}/{report_name}/{id}"
    return _download_content(model.odoo, url)


#######################################
# IMPORT AND EXPORT


def make_batches(
    data: Iterable[Dict], *, batch_size: int = 1000, group_by: str = None
) -> Iterable[List[Dict]]:
    """Split an interable to a batched iterable

    :param data: The iterable
    :param batch_size: Target batch size (default: 1000)
    :param group_by: field to group by (the value is kept in a single batch
    :return: An iterable of batches
    """
    batch: List[Dict] = []
    if group_by:
        data = sorted(data, key=lambda d: d[group_by])
        group_value = None
        for d in data:
            current_value = d[group_by]
            if len(batch) >= batch_size and group_value != current_value:
                yield batch
                batch = [d]
            else:
                batch.append(d)
            group_value = current_value
    else:
        for d in data:
            batch.append(d)
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def load_data(
    model: OdooModel,
    data: Iterable,
    *,
    method: str = "load",
    method_row_type=None,
    fields: Optional[List[str]] = None,
    formatter: Formatter = None,
):
    """Load the data into the model.

    The method is executed given as parameter the formatted data
    and when row type is list, fields is also passed by keyword.
    If the row type is list and no fields are given, the first row is used.

    The default method used is `load` where field name's "." are replaced with
    "/" to make it work.
    `write` is handled specially, by making write() and create() calls.
    You can use `create` to insert new records.
    Otherwise, the model can have a custom method you could use.

    :param model: The model
    :param data: The list of rows (dict or list)
    :param method: The name of the method to call
    :param method_row_type: The type of the rows; dict (default) or list
    :param fields: List of field name for list rows
    :param formatter: The formatter to use
    :return: The result of the method call
    """
    log = logging.getLogger(__name__)

    if method == 'load':
        method_row_type = list
    elif method_row_type is None or method in ('create', 'write'):
        method_row_type = dict
    log.debug("Load: %s(), row type is %s", method, method_row_type)

    if formatter is None:
        formatter = Formatter(model)

    log.info("Load: convert and format data")
    if method_row_type == dict:
        data = __convert_to_type_dict(data, fields)
        data = [formatter.format_dict(d) for d in data]
    elif method_row_type == list:
        data, fields = __convert_to_type_list(data, fields)
        data = [[formatter.format_function[fields[i]](v) for i, v in enumerate(d)] for d in data]
    else:
        raise Exception('Unsupported method row type: %s' % method_row_type)

    log.info("Load data using %s.%s(), %d records", model.model, method, len(data))
    if method == 'load':
        fields = [f.replace('.', '/') for f in cast(List[str], fields)]
        return model.execute(method, fields=fields, data=data)
    if method == 'write':
        return __load_data_write(model, data)
    if fields:
        return model.execute(method, data, fields=fields)
    return model.execute(method, data)


def __convert_to_type_list(
    data: Iterable, fields: Optional[List[str]]
) -> Tuple[Iterable[List], List[str]]:
    idata = iter(data)
    first_row = next(idata, None)
    if first_row is None:
        return [], fields or ['id']
    if not isinstance(first_row, list):
        if not fields:
            raise RuntimeError('Missing fields to convert into type list')
        data = ([d.get(f) for f in fields] for d in data)
    elif fields is None:
        logging.getLogger(__name__).debug("Load: using first row as field names")
        fields = first_row
        data = idata
    elif not isinstance(data, list):
        data = [first_row] + list(data)
    return data, fields


def __convert_to_type_dict(data: Iterable, fields: Optional[List[str]]) -> Iterable[Dict]:
    idata = iter(data)
    first_row = next(idata, None)
    if first_row is None:
        return []
    if isinstance(first_row, list):
        if fields is None:
            fields = first_row
            data = (dict(zip(fields, d)) for d in idata)
        else:
            if not isinstance(data, list):
                data = [first_row] + list(idata)
            if fields:
                data = ({f: d[i] for i, f in enumerate(fields)} for d in data)
    elif not isinstance(data, list):
        data = [first_row] + list(idata)
    return data


def __load_data_write(model: OdooModel, data: List[Dict]) -> Dict:
    """Use multiple write() and create() calls to update data

    :return: {'write_count': x, 'create_count': x, 'ids': [list of ids]}
    """
    create_data = []
    ids = []
    for d in data:
        id = d.pop('id')
        if id:
            model.execute('write', id, d)
            ids.append(id)
        else:
            create_data.append(d)
            ids.append(0)
    if create_data:
        created_ids = model.execute('create', create_data)
        iids = iter(created_ids)
        for i in range(len(ids)):
            if not ids[i]:
                ids[i] = next(iids)
        assert next(iids, None) is None
    return {
        'write_count': len(data) - len(create_data),
        'create_count': len(create_data),
        'ids': ids,
    }


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
    log = logging.getLogger(__name__)
    odoo = model.odoo
    kwargs = {}

    if isinstance(filter_or_domain, str):
        log.debug('Get the filter from Odoo: %s', filter_or_domain)
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
        log.debug('Get the export lines: %s', export_or_fields)
        fields = odoo['ir.exports.line'].search_read(
            [
                ('export_id.name', '=', export_or_fields),
                ('export_id.resource', '=', model.model),
            ],
            ['name'],
        )
        fields = [f['name'].replace('/', '.') for f in fields]
    else:
        log.debug('List of fields to export: %s', export_or_fields)
        fields = export_or_fields
    if not fields:
        raise ValueError('No fields to export')

    log.info('Export: execute search on %s', model.model)
    records = model.search_read_dict(domain, fields)

    log.info('Export: done, cleaning data')
    data = flatten(records, fields, expand_many=expand_many)
    if with_header:
        data.insert(0, [str(f) for f in fields])
    return data


def add_fields(
    model: OdooModel, data: List[Dict], by_field: str, fields: List[str] = ['id'], domain: List = []
):
    """Add fields by querying the model

    :param model: The model
    :param data: The list of dicts
    :param by_field: The field name to use to find other fields
    :param fields: The fields to get (default: ['id'])
    :param domain: Additional domain to use
    :raises Exception: When multiple results have the same by_field key
    """
    domain_by_field: List[Any] = [(by_field, 'in', [d[by_field] for d in data])]
    domain = ['&'] + domain_by_field + (domain if domain else domain_by_field)
    fetched_data = model.search_read_dict(domain, fields + [by_field])
    index = {d.pop(by_field): d for d in fetched_data}
    if len(index) != len(fetched_data):
        raise Exception('%s is not unique in %s when adding fields' % (by_field, model.model))
    for d in data:
        updates = index.get(d[by_field])
        if updates:
            d.update(updates)
        else:
            d.update({f: None for f in fields})


def add_xml_id(model: OdooModel, data: List, *, id_name='id', xml_id_field='xml_id'):
    """Add a field containg the xml_id

    :param model: The model
    :param data: The list of dicts or rows (list to append to)
    :param id_name: The name of the field to get the resource ids (default: 'id')
    :param xml_id_field: The name of the xmlid field (default: 'xml_id')
    """
    if id_name != 'id':
        relation = model.fields()[id_name].get('relation')
        model = model.odoo.get_model(cast(str, relation), check=True)
    id_index: Optional[int] = None
    ids = set()
    for row_num, row in enumerate(data):
        if isinstance(row, dict):
            ids.add(row[id_name])
        elif isinstance(row, list):
            if row_num == 0:
                id_index = row.index(id_name)
            else:
                ids.add(row[cast(int, id_index)])
        else:
            raise TypeError('Cannot append the url to %s' % type(row))
    xml_ids = {
        i['res_id']: i['complete_name']
        for i in model.odoo['ir.model.data'].search_read(
            [('model', '=', model.model), ('res_id', 'in', list(ids))],
            ['complete_name', 'res_id'],
        )
    }
    if id_index is None:
        # we have dicts
        for row in data:
            row[xml_id_field] = xml_ids.get(row[id_name], False)
    else:
        # we have a list
        for row_num, row in enumerate(data):
            if row_num == 0:
                row.append(xml_id_field)
            else:
                row.append(xml_ids.get(row[id_index], False))


def add_url(
    model: OdooModel,
    data: List,
    *,
    url_field='url',
    model_id_func=None,
    build_url=lambda _r, model_name, id: f"/web#model={model_name}&id={id}",
):
    """Add an URL field to data

    :param model: The model
    :param data: The list of dicts or rows (list to append to)
    :param url_field: The name of the URL field (default: 'url')
    :param model_id_func: The function to get a tuple (model_name, id)
    :param build_url: Function to build the URL (record, model_name, id) -> "/web..."
    """
    base_url = model.odoo.url
    if not model_id_func and data:
        if isinstance(data[0], list):
            model_id_func = lambda r: (model.model, r[0])  # noqa: E731
        else:
            model_id_func = lambda d: (model.model, d['id'])  # noqa: E731
    for row_num, row in enumerate(data):
        model_name, id = model_id_func(row)
        url = build_url(row, model_name, id)
        if url:
            url = urljoin(base_url, url)
        if isinstance(row, dict):
            row[url_field] = url
        elif isinstance(row, list):
            if row_num == 0:
                row.append(url_field)
            else:
                row.append(url)
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


def _expand_many(data: List[Dict]) -> Iterator[Dict]:
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
    'list_attachments',
    'get_report',
    'list_reports',
    'Formatter',
    'make_batches',
    'load_data',
    'export_data',
    'add_fields',
    'add_url',
    'add_xml_id',
]
