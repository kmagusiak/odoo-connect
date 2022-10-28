import pytest

from odoo_connect.explore import Instance, explore


@pytest.fixture(scope='function')
def odoo_cli_partner(odoo_cli, odoo_json_rpc_handler) -> Instance:
    handler = odoo_json_rpc_handler
    data = [{'id': 1, 'name': 'test'}, {'id': 2, 'name': 'demo'}]
    for d in data:
        d['display_name'] = d['name']

    def read_partner(ids, fields=[]):
        if not fields:
            fields = data[0].keys()
        elif 'id' not in fields:
            fields = ['id'] + fields
        return [{k: v for k, v in d.items() if k in fields} for d in data if d['id'] in ids]

    handler.patch_execute_kw('res.partner', 'read')(read_partner)

    @handler.patch_execute_kw('res.partner', 'search_read')
    def read_search_partner(domain, fields=[]):
        print('read_search_partner', domain)
        return read_partner([1], fields=fields)

    @handler.patch_execute_kw('res.partner', 'fields_get')
    def read_fields_partner(allfields=[], attributes=[]):
        attr = {a: False for a in attributes}
        attr['store'] = True
        return {
            'id': {**attr, 'type': 'int', 'string': 'ID'},
            'name': {**attr, 'type': 'char', 'string': 'Name'},
            'display_name': {**attr, 'type': 'char', 'string': 'Display Name', 'store': False},
        }

    @handler.patch_execute_kw('res.partner', 'create')
    def create(val_list):
        id = max(d['id'] for d in data)
        result = []
        for d in val_list:
            id += 1
            d['id'] = id
            data.append(d)
            result.append(id)
        return result

    @handler.patch_execute_kw('res.partner', 'write')
    def write(ids, values):
        for d in data:
            if d['id'] in ids:
                d.update(values)
        return True

    partner = explore(odoo_cli['res.partner'])
    partner.invalidate_cache()
    return partner


def test_explore(odoo_cli):
    obj = explore(odoo_cli['res.partner'])
    assert obj._model.model == 'res.partner'
    assert not obj
    obj = obj.browse(9)
    assert obj
    assert obj.ids == [9]


def test_ex_read(odoo_cli_partner: Instance):
    inst = odoo_cli_partner
    inst = inst.browse(1)
    data = inst.read()
    assert data[0]['name'] == 'test'
    assert inst.name == 'test'


def test_ex_search(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.search([('name', '=', 'test')])
    assert len(inst) == 1


def test_ex_cache(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.browse(1).cache(['display_name'])
    assert isinstance(inst, Instance)
    assert inst.display_name


def test_ex_exist(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.browse(*range(10)).exists()
    assert 0 < len(inst) < 10


def test_ex_combine(odoo_cli_partner: Instance):
    a = odoo_cli_partner.browse(5, 6)
    b = odoo_cli_partner.browse(6, 7)
    assert len(a + b) == 4
    assert (a - b).ids == [5]
    assert (a | b).ids == [5, 6, 7]
    assert (a & b).ids == [6]


def test_ex_filtered(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.browse(1, 2)
    assert len(inst) == 2
    inst = inst.filtered(lambda i: i.name == 'test')
    assert len(inst) == 1


def test_ex_create(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.create({'name': 'ok'})
    assert inst
    assert inst.name == 'ok'


def test_ex_write(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.browse(1)
    assert inst.name == 'test'
    inst.name = 'ok'
    assert inst.name == 'ok'


def test_ex_write_format(odoo_cli_partner: Instance):
    inst = odoo_cli_partner.browse(1)
    assert inst.name == 'test'
    inst.write({'name': ''}, format=True)
    assert inst.name is False
