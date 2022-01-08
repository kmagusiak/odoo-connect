import json

import pytest
from werkzeug.wrappers import Request, Response


class OdooMockedException(Exception):
    """Exception not reraised during a mocked rpc call"""

    pass


class OdooRPCHandler:
    """Used as a handler for Requests"""

    def __init__(self):
        self.call_generic = []
        self.call_execute_kw = []

    def execute_kw(
        self, database: str, uid: int, password: str, model: str, function: str, a: list, kw: dict
    ):
        """Implement execute_kw behaviour, just checks that the user is authenticated (any uid)"""
        assert database and uid > 0 and password, "Must be authenticated"
        for f in self.call_execute_kw:
            r = f(model, function, a, kw)
            if r is not None:
                return r
        pytest.fail('execute_kw not implemented for %s.%s' % (model, function))

    def generic(self, service: str, method: str, args: list):
        """Implement the call method from odoo"""
        if service == 'object' and method == 'execute_kw':
            return self.execute_kw(*args)
        for f in self.call_generic:
            r = f(service, method, args)
            if r is not None:
                return r
        pytest.fail('%s.%s not implemented' % (service, method))

    def patch_generic(self, f):
        """Append a method to `generic` call.

        If the method returns None, another one is tried.

        :param f: f(service, method, args) used for generic calls
        """
        self.call_generic.append(f)
        return f

    def patch_execute_kw(self, model, function):
        """Append a method to `execute_kw` call.

        If the method returns None, another one is tried.

        :param model: Model for the object's execute_kw
        :param function: Function name
        :return: Decorator for a function call where arguments will be expanded
        """

        def _patch_execute_kw(f):
            def checked_f(model_, function_, a, kw):
                if model == model_ and function == function_:
                    return f(*a, **kw)

            self.call_execute_kw.append(checked_f)
            return checked_f

        return _patch_execute_kw

    def __call__(self, request: Request):
        """Handle a jsonrpc request for the method call"""
        assert request.content_type == "application/json"
        data = request.json
        assert data["jsonrpc"] == "2.0" and data["id"]
        assert data["method"] == "call", "Only call method is implemented"
        status = 200
        output = {
            "jsonrpc": "2.0",
            "id": data["id"],
        }
        try:
            params = data["params"]
            output["result"] = self.generic(**params)
        except Exception as e:
            status = 500
            output["error"] = str(e)
            if not isinstance(e, OdooMockedException):
                raise  # don't try to transform errors during testing
        return Response(json.dumps(output), status=status, content_type="application/json")


def default_rpc_handler():
    """Instantiates a default handler. Serves as an example code too."""
    h = OdooRPCHandler()

    @h.patch_generic
    def version(service, method, args):
        if service == 'common' and method == 'version':
            return {"server_version": "15.0", "server_serie": "mocked"}

    @h.patch_generic
    def authenticate(service, method, args):
        if method == 'login':
            args = args + [{}]
            method = 'authenticate'
        if service == 'common' and method == 'authenticate':
            database, username, password, env = args
            if username == 'admin' and password == 'admin':
                return 1
            if username and username == password:
                return 2
            raise OdooMockedException('Cannot authenticate on %s with %s' % (database, username))

    @h.patch_execute_kw('res.users', 'read')
    def read_user(id, fields=[]):
        if not (0 < id < 10):
            return None  # not implemented for other id's
        result = {
            'id': id,
            'login': 'admin' if id == 1 else 'other',
            'name': 'some user',
            'parnter_id': [id, 'Contact'],
        }
        if fields:
            fields = ['id'] + fields
            result = {k: v for k, v in result.items() if k in fields}
        return [result]

    return h
