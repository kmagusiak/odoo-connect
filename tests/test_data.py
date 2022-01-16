import math
from datetime import datetime

import pytest

import odoo_connect.data as odoo_data


def test_binary_encoding():
    bin = b'OK'
    value = odoo_data.get_formatter('binary')(bin)
    assert isinstance(value, str)
    assert len(value) == math.ceil(len(bin) / 3) * 4

    original = odoo_data.decode_bytes(value)
    assert isinstance(original, bytes) and original == bin


def test_binary_encoding_empty():
    assert odoo_data.get_formatter('binary')(b'') is False


@pytest.mark.parametrize(
    "type_name,input,expected",
    [
        ('char', 'test', 'test'),
        ('int', 3, 3),
        ('date', datetime(2020, 2, 2, 3), "2020-02-02"),
        ('date', "2020-02-02 03:00:00.3", "2020-02-02"),
        ('datetime', datetime(2020, 2, 2, 3, microsecond=3), "2020-02-02 03:00:00"),
        ('datetime', "2020-02-02 03:00:00.3", "2020-02-02 03:00:00"),
        ('binary', b'', False),
        ('char', '', False),
    ],
)
def test_formatter(type_name, input, expected):
    assert odoo_data.get_formatter(type_name)(input) == expected


def test_add_url(odoo_cli):
    model = odoo_cli['res.partner']
    data = [{'id': 4}]
    odoo_data.add_url(model, data)
    url = data[0]['url']
    assert url.startswith('http')
    assert 'model=res.partner' in url
    assert 'id=4' in url


def test_add_url_list(odoo_cli):
    model = odoo_cli['res.partner']
    data = [[4]]
    odoo_data.add_url(model, data)
    assert model.model in data[0][1]


@pytest.mark.parametrize(
    "dict,fields,expected",
    [
        ({'id': 5}, ['id'], [5]),
        ({'id': 5, 'name': 'test'}, ['name'], ['test']),
        (
            {'id': 5, 'partner_id': {'name': 'partner_name'}},
            ['id', 'partner_id.name'],
            [5, 'partner_name'],
        ),
    ],
)
def test_flatten(dict, fields, expected):
    output = odoo_data.flatten([dict], fields)[0]
    assert expected == output


@pytest.mark.parametrize(
    "list_dict,fields,expected",
    [
        ([], ['id'], []),
        (
            [{'partner_id': {'name': 'nn'}, 'order_id': [{'name': 'S1'}, {'name': 'S2'}]}],
            ['partner_id.name', 'order_id.name'],
            [['nn', ['S1', 'S2']]],
        ),
    ],
)
def test_flatten_many(list_dict, fields, expected):
    output = odoo_data.flatten(list_dict, fields)
    assert expected == output


def test_flatten_expand_many():
    expanded = list(
        odoo_data.flatten(
            [
                {
                    'id': 5,
                    'numbers': [2, False],
                    'orders': [{'name': 'ok'}, {'name': 'ko', 'partners': [1, 2]}],
                }
            ],
            ['numbers', 'orders.name', 'orders.partners'],
            expand_many=True,
        )
    )
    assert len(expanded) == 12
