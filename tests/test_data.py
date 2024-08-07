import pytest

import odoo_connect.data as odoo_data


def test_add_field(odoo_cli, odoo_json_rpc_handler):
    handler = odoo_json_rpc_handler

    @handler.patch_execute_kw('res.partner', 'read')
    def read_partner(id, fields=[], load=None):
        return [{'id': 1, 'name': 'test'}]

    @handler.patch_execute_kw('res.partner', 'search_read')
    def read_search_partner(domain, fields=[], load=None):
        print(domain)
        data = [{'id': 1, 'name': 'test'}]
        if not fields:
            return data
        if 'id' not in fields:
            fields += 'id'
        return [{k: v for k, v in d.items() if k in fields} for d in data]

    @handler.patch_execute_kw('res.partner', 'fields_get')
    def read_fields_partner(allfields=[], attributes=[]):
        attr = {a: a == 'store' for a in attributes}
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
    def read_search_data(domain, fields=[], load=None):
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
    result = odoo_data.flatten([dict], fields)
    output = next(iter(result))
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
    output = list(odoo_data.flatten(list_dict, fields))
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


def test_export(odoo_cli):
    model = odoo_cli['res.users']
    data = odoo_data.export_data(model, [], ['login'])
    print(data.schema)
    assert len(data) > 0, "No data"
    assert data.schema[0]['type'] == "char", "Invalid login type"
    assert data.column_names == ['login']
    assert str(data.get_sql_columns()[0]) == 'login varchar'


def test_batches():
    b = list(odoo_data.make_batches([1, 2, 3]))
    assert b == [[1, 2, 3]], "simple batch"
    b = list(odoo_data.make_batches([1, 2, 3], batch_size=2))
    assert b == [[1, 2], [3]], "small batches"
    source = [*[{'a': 'ok', 'v': i} for i in range(5)], {'a': 'z', 'v': 0}]
    b = list(odoo_data.make_batches(source, batch_size=2, group_by="a"))
    assert b == [source[0:5], source[5:]], "group by"
    source = [{'a': 'x'}, {'a': 'b'}]
    b = list(odoo_data.make_batches(source, group_by="a"))
    assert b == [sorted(source, key=lambda i: i['a'])], "group by should sort"


def test_batches_no_key():
    with pytest.raises(KeyError):
        list(odoo_data.make_batches([{}], batch_size=2, group_by="a"))


def test_load(odoo_cli, odoo_json_rpc_handler):
    model = odoo_cli['res.users']
    handler = odoo_json_rpc_handler

    @handler.patch_execute_kw(model.model, 'load')
    def load_model(fields, data):
        return "loaded"

    r = odoo_data.load_data(model, [{'login': 'x'}], fields=["login"])
    assert r == "loaded"
