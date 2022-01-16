import odoo_connect.data as odoo_data


def test_get_attachment(odoo_session):
    model = odoo_session['account.move']
    value = odoo_data.get_attachment(model, 1)
    assert isinstance(value, bytes) and len(value) > 1


def test_get_attachment_field(odoo_session):
    model = odoo_session['res.users']
    ids = model.search([('image_1920', '!=', False)], limit=1)
    value = odoo_data.get_attachment(model, ids[0], 'image_1920')
    assert isinstance(value, bytes) and len(value) > 1


def test_get_attachment_bytes(odoo_session):
    bin = bytes("hello", 'ascii')
    value = odoo_data.get_attachment(odoo_session['res.partner'], odoo_data.format_binary(bin))
    assert bin == value


def test_get_attachments(odoo_session):
    values = odoo_data.get_attachments(odoo_session, [1, 2])
    assert len(values) == 2
    assert all(isinstance(name, str) and isinstance(raw, bytes) for name, raw in values)
