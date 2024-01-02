# Odoo Connect

A simple library to use Odoo RPC.

[![PyPI version](https://badge.fury.io/py/odoo-connect.svg)](https://pypi.org/project/odoo-connect/)

## Usage

```python
import odoo_connect
odoo = env = odoo_connect.connect(url='http://localhost:8069', username='admin', password='admin')
so = env['sale.order']
so.search_read([('create_uid', '=', 1)], [])
```

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
However, RPC client libraries will perform multiple steps, on a failure,
already executed code was committed. You can end with race conditions
where some other code sets product_uom_qty to 0 before you increment it.
A better way of doing this is to implement a function on Odoo side and call it.

```python
lines = env['sale.order.line'].search([
	('order_id.name', '=', 'S00001')
])
# this is fine on the server, but not in RPC (multiple transactions)
for line in lines:
	if line.product_uom_qty > 1:
		line.product_uom_qty += 1
# single transaction
lines.increment_qty([('product_uom_qty', '>', 1)])
```

## Export and import data

A separate package provides utilities to more easily extract data from Odoo.
It also contains utility to get binary data (attachments) and reports;
however this requires administrative permissions.

Since Odoo doesn't accept all kind of values, the `format` package will help
with converting between python values and values returned by Odoo.

The provided function will return a table-like (list of lists) structure
with the requested data.
You can also pass `ir.filters` names or `ir.exports` names instead of,
respectively, domains and fields. Note that this doesn't support groupping.

```python
import odoo_connect.data as odoo_data
so = env['sale.order']

# Read data as usual
data = so.search_read_dict([('state', '=', 'sale')], ['name', 'partner_id.name'])
so.read_group([], ['amount_untaxed'], ['partner_id', 'create_date:month'])
odoo_data.add_url(so, data)

# Exporting flattened data
all_data = odoo_data.export_data(so, [('state', '=', 'sale')], ['name', 'partner_id.name'])
with io.StringIO(newline='') as f:
    w = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    w.writerows(all_data.to_csv())
all_data.to_pandas()  # as a data frame
all_data.to_dbapi(con, 'table_name')  # create a table

# Import data using Odoo's load() function
odoo_data.load_data(so, data)

# Import data using writes and creates (or another custom method)
for batch in odoo_data.make_batches(data):
	# add ids by querying the model using the 'name' field
	# if you remove 'id' from the data, only create() is called
	odoo_data.add_fields(so, batch, 'name', ['id'])
	odoo_data.load_data(so, batch, method='write')
```

## Explore

Provides a simple abstraction for querying data with a local cache.
It may be easier than executing and parsing a `read()`.
Also, auto-completion for fields is provided in jupyter.

```python
from odoo_connect.explore import explore
sale_order = explore(env['sale.order'])
sale_order = sale_order.search([], limit=1)
sale_order.read()
```

## Development

You can use a vscode container and open this repository inside it.
Alternatively, clone and setup the repository manually.

```bash
git clone $url
cd odoo-connect
# Install dev libraries
pip install -r requirements.txt
./pre-commit install
# Run some tests
pytest
```
