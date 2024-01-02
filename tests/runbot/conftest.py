import logging
import os

import pytest

import odoo_connect


@pytest.fixture(scope='session')
def connect_params():
    # runbot is no longer accessible for jsonrpc,
    # try to get the server from the environment
    odoo_url = os.environ.get("ODOO_URL", "http://admin@localhost:8069/")
    version = "unknown"
    logging.info("Using odoo server %s: %s", version, odoo_url)

    return {
        'url': odoo_url,
    }


@pytest.fixture(scope='session')
def odoo_session(connect_params):
    return odoo_connect.connect(**connect_params)
