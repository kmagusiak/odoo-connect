import random

import requests
from requests.compat import urljoin

from . import odoo_rpc_base

__doc__ = """
Uses requests and json to call Odoo
"""


class OdooClientJSON(odoo_rpc_base.OdooClientBase):
    """Odoo Connection using JSONRPC"""

    def __init__(self, **kwargs):
        url = kwargs['url']
        self._json_url = urljoin(url, "jsonrpc")
        self.session = requests.Session()
        super().__init__(**kwargs)

    @property
    def protocol(self):
        return "jsonrpc"

    def _json_rpc(self, method, params):
        """Make a jsonrpc call"""
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": random.randint(0, 1000000000),
        }
        url = self._json_url
        req = self.session.post(url, json=data)
        try:
            reply = req.json()
        except Exception:
            raise Exception(req.content)
        if reply.get("error"):
            raise Exception(reply["error"])
        return reply.get("result", None)

    def _call(self, service, method, *args):
        return self._json_rpc("call", {"service": service, "method": method, "args": args})
