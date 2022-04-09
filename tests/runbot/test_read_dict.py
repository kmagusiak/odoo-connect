import re


def test_read_dict(odoo_session):
    data = odoo_session['res.users'].read_dict(
        [1],
        ['login', 'partner_id.name', 'partner_id.commercial_partner_id.name'],
    )
    print(data)
    user = data[0]
    assert user['id'] == 1
    assert 'login' in user
    partner = user['partner_id']
    assert 'id' in partner
    assert isinstance(partner.get('commercial_partner_id'), dict)


def test_read_one_dict(odoo_session):
    user = odoo_session['res.users'].read_dict(
        1,
        ['login'],
    )
    assert isinstance(user, dict)
    assert 'login' in user


def test_search_read_dict(odoo_session):
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


def test_read_all_fields(odoo_session):
    user = odoo_session['res.users'].read_dict(1, [])
    assert isinstance(user.get('partner_id'), int)


def test_read_group(odoo_session):
    data = odoo_session['res.users'].read_group_dict([], [], ['create_date:month'])
    assert data[0]['__count']
    month = data[0]['create_date:month']
    assert re.match(r'\d{4}-\d{2}', month), 'Date is not in ISO format'
