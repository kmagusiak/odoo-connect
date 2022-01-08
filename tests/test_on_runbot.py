import logging
import re

import pytest
import requests

import odoo_connect

pytestmark = pytest.mark.runbot


@pytest.fixture(scope='session')
def connect_params():
    runbot_page = requests.get('https://runbot.odoo.com/')
    odoo_url = "http://localhost/"
    version = ""
    # we don't use (yet) any XML parsing to keep dependencies simple
    # find one of the following and select a URL
    # - bundle href (row and name of the branch)
    # - link to a sign-in action
    for m in re.finditer(
        r'href="/runbot/(bundle)[^<]+<b>([^<]*)</b>'
        r'|<a class="[^"]*fa-(sign-in)[^"]*" href="([^"]*)"',
        runbot_page.text,
    ):
        if m.group(1) == 'bundle':
            version = m.group(2)
        elif version and re.match(r'^\d+\.\d$', version) and m.group(3) == 'sign-in':
            odoo_url = m.group(4)
            break
    odoo_url = odoo_url.replace('http://', 'https://')
    logging.info("Using odoo server %s: %s", version, odoo_url)

    return {
        'url': odoo_url,
        'username': 'admin',
        'password': 'admin',
    }


@pytest.fixture(scope='session')
def odoo_session(connect_params):
    return odoo_connect.connect(**connect_params)


@pytest.mark.parametrize("rpctype", ['jsonrpc', 'xmlrpc'])
def test_user_with_protocol(connect_params, rpctype):
    env = odoo_connect.connect(**connect_params, rpctype=rpctype)
    user = env.user
    print(user)
    assert isinstance(user, dict), "Failed to get a response"
    assert user['login'] == connect_params['username']


def test_version(connect_params):
    env = odoo_connect.connect(connect_params['url'])
    version = env.version()
    print(version)
    assert isinstance(version, dict)
