import xmlrpc.client

from . import odoo_rpc_base

__doc__ = """
Uses xmlrpc for the client.
"""


def _urljoin(base, *parts):
    if not parts:
        return base
    if base.endswith("/"):
        base = base[:-1]
    return "/".join([base] + [p.strip("/") for p in parts])


class OdooClientXML(odoo_rpc_base.OdooClientBase):
    """Odoo Connection using XMLRPC"""

    def __init__(self, **kwargs):
        base_url = kwargs['url']
        self.client = {
            name: xmlrpc.client.ServerProxy(_urljoin(base_url, "xmlrpc/2", name))
            for name in ('common', 'object')
        }
        super().__init__(**kwargs)

    @property
    def protocol(self):
        return "xmlrpc"

    def _call(self, service, method, *args):
        cli = self.client.get(service)
        m = cli and getattr(cli, method, None)
        if not m:
            raise Exception('Service {service} does not have {method}')
        return m(*args)
