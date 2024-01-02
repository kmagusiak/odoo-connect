import pytest

import odoo_connect.data as odoo_data


def test_list_reports(odoo_session):
    model = odoo_session['account.move']
    reports = odoo_data.list_reports(model)
    assert all(d.get('report_name') for d in reports)


@pytest.mark.skip("The session credentials seems not passed since v16")
def test_get_report(odoo_session):
    model = odoo_session['account.move']
    ids = model.search(
        [('state', '=', 'posted'), ('move_type', '=', 'in_invoice')], limit=1, order='id'
    )
    value = odoo_data.get_report(model, 'account.report_invoice', ids[0])
    assert isinstance(value, bytes) and len(value)
