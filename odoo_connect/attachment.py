import logging
from typing import Dict, List, Optional, overload

from .format import decode_binary
from .odoo_rpc import OdooClient, OdooModel, urljoin

__doc__ = """Manage attachments and reports

Export binary data from Odoo.
Note that since version 16, the jsonrpc authentication does not set cookies
anymore, so this module may become useless or deprecated in the future.
"""


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
    model: OdooModel, id: int = 0, field_name: str = '', encoded_value: Optional[str] = None
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

        def attachment_url(d, _model_name=None, _id=None):
            url = d.get('url') or d.get('website_url')
            if url and d.get('public'):
                return url
            if url and d.get('access_token'):
                url += ('&' if '?' in url else '?') + 'access_token=' + d.get('access_token')
                return url
            return False

        for d in data:
            d[url_field] = attachment_url(d)
    return data


def _download_content(
    odoo: OdooClient, url: str, *, params: Dict = {}, access_token: Optional[str] = None
) -> bytes:
    """Download contents from a URL"""
    log = logging.getLogger(__name__)
    session = odoo.session
    if not session:
        raise RuntimeError('Odoo client must have a session to download contents')
    if odoo.major_version >= 16 and access_token is None:
        log.warning("Since version 16, the session may be unauthenticated")
        # otherwise, the session is authenticated.

    url = urljoin(odoo.url, url)
    params = {}
    if access_token:
        params = {**params, 'access_token': access_token}
    log.info("Get content: %s", url)
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


__all__ = [
    'get_attachment',
    'get_attachments',
    'list_attachments',
    'get_report',
    'list_reports',
]
