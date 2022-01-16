import pathlib

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


def pytest_collection_modifyitems(config, items):
    # If a test is in a subdirectory, add marker which is the directory name
    # https://stackoverflow.com/questions/57031403/pytest-marks-mark-entire-directory-package
    # To mark a file, you can use pytestmark = pytest.mark.my_mark
    rootdir = pathlib.Path(config.rootdir)
    for item in items:
        rel_path = pathlib.Path(item.fspath).relative_to(rootdir)
        mark_name = next((part for part in rel_path.parts if not part.startswith('test')), '')
        if mark_name:
            mark = getattr(pytest.mark, mark_name)
            item.add_marker(mark)
