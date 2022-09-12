# Odoo Connect

A simple library to use Odoo RPC.

[![PyPI version](https://badge.fury.io/py/odoo-connect.svg)](https://pypi.org/project/odoo-connect/)

## Usage

	import odoo_connect
	odoo = env = odoo_connect.connect(url='http://localhost', username='admin', password='admin')
	so = env['sale.order']
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

## Export and import data

A separate package provides utilities to more easily extract data from Odoo.
It also contains utility to get binary data (attachments) and reports.

The following function will return a table-like (list of lists) structure
with the requested data.
You can also pass filter names or export names instead of, respectively,
domains and fields. Note that this doesn't support groupping.

	# Read data as usual
	env['sale.order'].search_read_dict([('state', '=', 'sale')], ['name', 'partner_id.name'])
	env['sale.order'].read_group([], ['amount_untaxed'], ['partner_id', 'create_date:month'])

	# Export data
	import odoo_connect.data as odoo_data
	so = env['sale.order']
	data = odoo_data.export_data(so, [('state', '=', 'sale')], ['name', 'partner_id.name'])
	odoo_data.add_url(so, data)

	# Import data using Odoo's load() function
	odoo_data.load_data(so, data)

	# Import data using writes and creates (or another custom method)
	for batch in odoo_data.make_batches(data):
		# add ids by querying the model using the 'name' field
		odoo_data.add_fields(so, batch, 'name', ['id'])
		# if you just plan to create(), you can skip adding ids
		odoo_data.load_data(partner, batch, method='write')

## Explore

	from odoo_connect.explore import explore
	sale_order = explore(env['sale.order'])
	sale_order = sale_order.search([], limit=1)
	sale_order.read()


## Development

You can use a vscode container and open this repository inside it.
Alternatively, clone and setup the repository manually.

	git clone $url
	cd odoo-connect
	# Install dev libraries
	pip install -r requirements.txt
	./pre-commit install
	# Run some tests
	pytest
