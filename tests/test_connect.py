import pytest

import odoo_connect


@pytest.mark.parametrize(
    "rpctype",
    [
        None,
        'jsonrpc',
        pytest.param('xmlrpc', marks=pytest.mark.skip('xmlrpc testing not implemented')),
    ],
)
def test_connect_and_check_user(connect_params, rpctype):
    if rpctype:
        connect_params = {**connect_params, 'rpctype': rpctype}
    env = odoo_connect.connect(**connect_params)
    assert env.protocol == (rpctype or 'jsonrpc')
    user = env.user
    print(user)
    assert isinstance(user, dict)
    assert user['login'] == connect_params['username']


def test_invalid_rpc_type():
    with pytest.raises(TypeError):
        odoo_connect.connect('')


def test_database(odoo_cli):
    assert odoo_cli.database == 'odoo', "Odoo should be the default database"


@pytest.mark.tryfirst
def test_version(connect_params):
    env = odoo_connect.connect(connect_params['url'])
    version = env.version()
    print(version)
    assert isinstance(version, dict)
