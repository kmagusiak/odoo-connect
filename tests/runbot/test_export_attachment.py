import odoo_connect.data as odoo_data
from odoo_connect.format import format_binary


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
    value = odoo_data.get_attachment(odoo_session['res.partner'], encoded_value=format_binary(bin))
    assert bin == value


def test_get_attachments(odoo_session):
    values = odoo_data.get_attachments(odoo_session, [1, 2])
    assert isinstance(values, dict) and values
