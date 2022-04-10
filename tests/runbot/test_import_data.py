import itertools

import odoo_connect.data as odoo_data


def test_make_batches():
    numbers = range(10)
    bnumbers = list(odoo_data.make_batches(numbers, batch_size=3))
    assert len(bnumbers) == 4


def test_make_batches_by_key():
    data = [
        {'letter': letter, 'i': i} for letter, i in zip(itertools.cycle(['a', 'b', 'c']), range(10))
    ]
    batches = odoo_data.make_batches(data, batch_size=5, group_by='letter')
    batch = next(batches)
    assert len(batch) == 7  # 4 a and 3 b
    batch = next(batches)
    assert len(batch) == 3  # 3 c
    assert next(batches, None) is None


def test_import(odoo_session):
    model = odoo_session['res.partner']
    data = [{'name': 'john'}]
    ids = odoo_data.load_data(model, data, method='create')
    assert len(ids) == 1


def test_import_create_rows(odoo_session):
    model = odoo_session['res.partner']
    data = [['name'], ['john row']]
    ids = odoo_data.load_data(model, data, method='create')
    assert len(ids) == 1
