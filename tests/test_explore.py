from odoo_connect.explore import explore


def test_read(odoo_cli, odoo_json_rpc_handler):
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
    inst = explore(model)
    inst = inst.browse(1)
    data = inst.read()
    assert data[0].get('name')  # TODO test this
    assert inst.name == 'test'
