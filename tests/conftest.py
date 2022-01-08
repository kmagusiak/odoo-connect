import pytest

from . import mock_odoo_server


@pytest.fixture(scope='function')
def connect_params(httpserver, odoo_json_rpc_handler):
    # use odoo_json_rpc_handler so it is set up
    return {
        'url': httpserver.url_for('/'),
        'username': 'admin',
    }


@pytest.fixture(scope='function')
def odoo_json_rpc_handler(httpserver):
    """Setup the http server for Odoo JSON RPC"""
    handler = mock_odoo_server.default_rpc_handler()
    httpserver.expect_request(
        "/jsonrpc", headers={'content-type': 'application/json'}
    ).respond_with_handler(handler)
    return handler


@pytest.fixture(scope='function')
def odoo_cli(connect_params):
    import odoo_connect

    return odoo_connect.connect(**connect_params)


# CONFIGURE PYTEST


def pytest_configure(config):
    config.addinivalue_line("markers", "runbot: integration tests on runbot")
