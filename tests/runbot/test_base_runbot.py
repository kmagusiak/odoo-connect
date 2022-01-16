import pytest

import odoo_connect


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
