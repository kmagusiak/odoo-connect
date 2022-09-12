import math
from datetime import datetime

import pytest

import odoo_connect.data as odoo_data


def test_binary_encoding():
    bin = b'OK'
    value = odoo_data.format_binary(bin)
    assert isinstance(value, str)
    assert len(value) == math.ceil(len(bin) / 3) * 4

    original = odoo_data.decode_bytes(value)
    assert isinstance(original, bytes) and original == bin


def test_binary_encoding_empty():
    assert odoo_data.format_binary(b'') == ''


@pytest.mark.parametrize(
    "type_name,func,input,expected",
    [
        ('char', 'default', 'test', 'test'),
        ('int', 'default', 3, 3),
        ('date', 'date', datetime(2020, 2, 2, 3), "2020-02-02"),
        ('date', 'date', "2020-02-02 03:00:00.3", "2020-02-02"),
        ('datetime', 'datetime', datetime(2020, 2, 2, 3, microsecond=3), "2020-02-02 03:00:00"),
        ('datetime', 'datetime', "2020-02-02 03:00:00.3", "2020-02-02 03:00:00"),
        ('binary', 'binary', b'', ''),
        ('char', 'default', '', False),
    ],
)
def test_format(type_name, func, input, expected):
    formatter = getattr(odoo_data, "format_%s" % func)
    assert formatter(input) == expected, "Couldn't format %s" % type_name


def test_formatter():
    f = odoo_data.Formatter()
    f['d'] = odoo_data.format_date
    f.field_map['X'] = 'y'
    f.field_map['removed'] = ''
    assert f.map_field('X') == 'y'
    d = f.format_dict({'d': '2022-01-01 15:10:05', 'X': 'value y', 'def': 'ok ', 'removed': 1})
    print(d)
    assert d['d'] == '2022-01-01'
    assert 'X' not in d and d['y'] == 'value y'
    assert d['def'] == 'ok'
    assert 'removed' not in d


def test_add_field(odoo_cli, odoo_json_rpc_handler):
    handler = odoo_json_rpc_handler

    @handler.patch_execute_kw('res.partner', 'read')
    def read_partner(id, fields=[]):
        return [{'id': 1, 'name': 'test'}]

    @handler.patch_execute_kw('res.partner', 'search_read')
    def read_search_partner(domain, fields=[]):
        print(domain)
        data = [{'id': 1, 'name': 'test'}]
        if not fields:
            return data
        if 'id' not in fields:
            fields += 'id'
        return [{k: v for k, v in d.items() if k in fields} for d in data]

    @handler.patch_execute_kw('res.partner', 'fields_get')
    def read_fields_partner(allfields=[], attributes=[]):
        attr = {a: True if a == 'store' else False for a in attributes}
        return {
            'id': {**attr, 'type': 'int', 'string': 'ID'},
            'name': {**attr, 'type': 'char', 'string': 'Name'},
        }

    model = odoo_cli['res.partner']
    data = model.read(1, ['name'])
    id = data[0].pop('id')
    odoo_data.add_fields(model, data, 'name', ['id'])
    assert data[0].get('id') == id


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
    data = [['id'], [4]]
    odoo_data.add_url(model, data)
    assert 'url' in data[0]
    assert model.model in data[1][1]


def test_add_xml_id(odoo_cli, odoo_json_rpc_handler):
    handler = odoo_json_rpc_handler

    @handler.patch_execute_kw('ir.model.data', 'search_read')
    def read_search_data(domain, fields=[]):
        print(domain)
        data = [{'id': 1, 'res_id': 4, 'model': 'res.partner', 'complete_name': 'test.myid'}]
        if not fields:
            return data
        if 'id' not in fields:
            fields += 'id'
        return [{k: v for k, v in d.items() if k in fields} for d in data]

    model = odoo_cli['res.partner']
    data = [{'id': 4}, {'id': 9}]
    odoo_data.add_xml_id(model, data)
    assert 'test.myid' == data[0]['xml_id']
    assert not data[1]['xml_id']


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
