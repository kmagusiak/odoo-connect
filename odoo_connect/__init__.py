import urllib.parse

from .odoo_rpc_base import OdooClientBase, OdooModel  # noqa

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
    """Connect to an odoo database.

    When infer_paramters is set, the url is parsed to get additional information.
    - When missing, the scheme is https (or http on localhost)
    - When missing we try the following heuristics: the database is read from the path,
      in a multipart host name, the first part is used, otherwise just "odoo"
    - The username and password are read if present in the url
    - When missing, the password is copied from the user

    Some examples for infered parameters:
    - https://user:pwd@hostname/database
    - mytest.odoo.com -> https://mytest.odoo.com/mytest
    - localhost -> http://localhost/odoo
    - https://admin@myserver:8069 would connect with password "admin" to "odoo" database

    :param url: The URL to the server, it may encode other information when infer_parameters is set
    :param database: The database name
    :param username: The username (when set, we try to authenticate the user during the connection)
    :param password: The password
    :param rpctype: The type of RPC (default: jsonrpc)
    :param infer_paramters: Whether to infer parameters (default: True)
    :return: Connection object to the Odoo instance
    """
    url = urllib.parse.urlparse(url)
    if infer_parameters:
        if not url.scheme and not url.netloc and url.path:
            # we just have a server name in the path (reparse with slashes)
            url = urllib.parse('//' + url.path.lstrip('/'))
        if not url.hostname:
            raise ValueError('No hostname in url %s' % url)
        if not database and len(url.path) > 1:
            # extract the database from the path if it's there
            path = url.path.lstrip('/')
            if '/' not in path:
                database = path
                url = url._replace(path='/')
        if not database:
            # try to extract the database from the hostname
            dot = url.hostname.find('.')
            if dot > 0:
                database = url.hostname[:dot]
        if not database:
            # by default set to odoo
            database = 'odoo'
        if not username and url.username:
            # read username and password from the url
            username = url.username
            password = url.password
        if not password and username:
            # copy username to password when not set
            password = username
        # make sure the url does not contain credentials anymore
        at_loc = url.netloc.find('@')
        if at_loc > 0:
            url = url._replace(netloc=url.netloc[at_loc + 1 :])
    if not url.scheme:
        # add a scheme
        url = url._replace(scheme="http" if url.host == "localhost" else "https")
    args = {
        'url': url.geturl(),
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
