import xmlrpc.client

from .odoo_rpc import OdooClient, OdooServerError, urljoin

__doc__ = """
Uses xmlrpc for the client.
Kept for backwards compatibility if needed.
"""


class OdooClientXML(OdooClient):
    """Odoo Connection using XMLRPC"""

    def _init_session(self):
        # no need to call super, we set just the client here
        base_url = self.url
        self._client = {
            name: xmlrpc.client.ServerProxy(urljoin(base_url, "xmlrpc/2", name))
            for name in ('common', 'db', 'object')
        }

    @property
    def protocol(self):
        return "xmlrpc"

    def _call(self, service, method, *args):
        cli = self._client.get(service)
        m = cli and getattr(cli, method, None)
        if not m:
            raise OdooServerError('Service {service} does not have {method}')
        return m(*args)
