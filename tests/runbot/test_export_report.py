import odoo_connect.data as odoo_data


def test_get_reports(odoo_session):
    model = odoo_session['account.move']
    reports = odoo_data.get_reports(model)
    assert all(d.get('report_name') for d in reports)


def test_get_report(odoo_session):
    model = odoo_session['account.move']
    value = odoo_data.get_report(model, 'account.report_invoice', 1)
    assert isinstance(value, bytes) and len(value)
