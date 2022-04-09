from pprint import pprint

import odoo_connect.data as odoo_data


def test_export(odoo_session):
    model = odoo_session['res.partner']
    fields = ['name', 'parent_id.name']
    data = odoo_data.export_data(model, [('id', '<', 10)], fields)
    pprint(data)
    assert fields == data[0]
    assert all(len(fields) == len(row) for row in data)
