import functools
import xmlrpc.client

from .odoo_rpc_base import OdooClientBase, OdooServerError, urljoin

__doc__ = """
Uses xmlrpc for the client.
"""


class OdooClientXML(OdooClientBase):
    """Odoo Connection using XMLRPC"""

    @functools.wraps(OdooClientBase.__init__)
    def __init__(self, **kwargs):
        base_url = kwargs['url']
        self.client = {
            name: xmlrpc.client.ServerProxy(urljoin(base_url, "xmlrpc/2", name))
            for name in ('common', 'db', 'object')
        }
        super().__init__(**kwargs)

    @property
    def protocol(self):
        return "xmlrpc"

    def _call(self, service, method, *args):
        cli = self.client.get(service)
        m = cli and getattr(cli, method, None)
        if not m:
            raise OdooServerError('Service {service} does not have {method}')
        return m(*args)
