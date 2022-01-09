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


def test_list_models(odoo_session):
    models = odoo_session.list_models()
    assert isinstance(models, list) and 'res.users' in models


def test_model_search_user(odoo_session):
    data = odoo_session['res.users'].search_read(
        [('active', 'in', [True, False])], ['login'], limit=2
    )
    print(data)
    assert len(data) == 2, "There should always be at least 2 users"
    assert data[0]['login'], "Every user must have a login"


def test_ref(odoo_session):
    data = odoo_session.ref('base.group_user', fields=['name'])
    print(data)
    assert isinstance(data, dict)


def test_read_dict(odoo_session):
    data = odoo_session['res.users'].search_read_dict(
        [('id', '=', 1), ('active', 'in', [True, False])],
        ['login', 'partner_id.name', 'partner_id.commercial_partner_id.name'],
    )
    print(data)
    user = data[0]
    assert user['id'] == 1
    assert 'login' in user
    partner = user['partner_id']
    assert 'id' in partner
    assert isinstance(partner.get('commercial_partner_id'), dict)
