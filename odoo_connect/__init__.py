__doc__ = """
Simple Odoo RPC library.
"""


def connect(
    url,
    database=None,
    username=None,
    password=None,
    rpctype='jsonrpc',
    infer_parameters=True,
):
    if not url:
        raise Exception('url must not be empty')
    if infer_parameters:
        if not url.startswith('http'):
            # assume url contains just the host name
            protocol = "http" if url == "localhost" else "https"
            url = f"{protocol}://{url}/"
        if not database:
            # try to extract from the URL
            slash, dot = url.find('//'), url.find('.')
            if 0 < slash < dot:
                database = url[slash + 2 : dot]
            # by default set to odoo
            if not database:
                database = 'odoo'
        if not password and username:
            # copy username to password
            password = username
    args = {
        'url': url,
        'database': database,
        'username': username,
        'password': password,
    }

    # Create the connection
    if rpctype == 'jsonrpc':
        from . import odoo_rpc_json

        return odoo_rpc_json.OdooClientJSON(**args)
    if rpctype == 'xmlrpc':
        from . import odoo_rpc_xml

        return odoo_rpc_xml.OdooClientXML(**args)
    raise NotImplementedError(f"rpctype '{rpctype}' not implemented")
