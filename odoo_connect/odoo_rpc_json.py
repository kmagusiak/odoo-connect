import functools
import random

import requests

from .odoo_rpc_base import OdooClientBase, OdooServerError, urljoin

__doc__ = """
Uses requests and json to call Odoo
"""


class OdooClientJSON(OdooClientBase):
    """Odoo Connection using JSONRPC"""

    @functools.wraps(OdooClientBase.__init__)
    def __init__(self, **kwargs):
        url = kwargs['url']
        self.__json_url = urljoin(url, "jsonrpc")
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
        resp = self.session.post(self.__json_url, json=data)
        resp.raise_for_status()
        reply = resp.json()
        if reply.get("error"):
            raise OdooServerError(reply["error"])
        return reply["result"]

    def _call(self, service, method, *args):
        return self._json_rpc("call", {"service": service, "method": method, "args": args})
