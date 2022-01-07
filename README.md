# Odoo Connect

A simple library to use Odoo RPC.

## Usage

	import odoo_connect
	odoo = odoo_connect.connect(url='http://localhost', username='admin', password='admin')
	so = odoo.env['sale.order']
	so.search_read([('create_uid', '=', 1)], [])

## Rationale

[OdooRPC](https://pypi.org/project/OdooRPC/)
or [Odoo RPC Client](https://pypi.org/project/odoo-rpc-client/)
are both more complete and mimic internal Odoo API.
Then [aio-odoorpc](https://pypi.org/project/aio-odoorpc/) provides
an asynchronous API.

This library provides only a simple API for connecting to the server
and call methods, so the maintenance should be minimal.

Note that each RPC call is executed in a transaction.
So the following code on the server, will add one to every line ordered
quantity or fail and do nothing.
However, ORM client libraries will perform multiple steps, on a failure,
already executed code was committed. You can also end with race conditions
where some other code set product_uom_qty to 0 before you increment it.

	lines = env['sale.order.line'].search([
		('order_id.name', '=', 'S00001')
	])
	for line in lines:
		if line.product_uom_qty > 1:
			line.product_uom_qty += 1
