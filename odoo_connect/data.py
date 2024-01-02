import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, cast

from .format import Formatter
from .odoo_rpc import OdooModel, urljoin

__doc__ = """Export and import data from Odoo.

To download values, use `export_data` for a flat tabular format.
To import, you can use `load_data` to upload data into Odoo.
Alternatively, you can use the formatter to prepare data for upload and
then call create or write methods.
"""


def make_batches(
    data: Iterable[Dict], *, batch_size: int = 1000, group_by: str = ''
) -> Iterable[List[Dict]]:
    """Split an interable to a batched iterable

    :param data: The iterable
    :param batch_size: Target batch size (default: 1000)
    :param group_by: field to group by (the value is kept in a single batch, can be empty)
    :return: An iterable of batches
    """
    batch: List[Dict] = []
    if group_by:
        data = sorted(data, key=lambda d: d[group_by])
        group_value = None
        for d in data:
            current_value = d[group_by]
            if len(batch) >= batch_size and group_value != current_value:
                yield batch
                batch = [d]
            else:
                batch.append(d)
            group_value = current_value
    else:
        for d in data:
            batch.append(d)
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def load_data(
    model: OdooModel,
    data: Iterable,
    *,
    method: str = "load",
    method_row_type=None,
    fields: Optional[List[str]] = None,
    formatter: Optional[Formatter] = None,
):
    """Load the data into the model.

    The method is executed given as parameter the formatted data
    and when row type is list, fields is also passed by keyword.
    If the row type is list and no fields are given, the first row is used.

    The default method used is `load` where field name's "." are replaced with
    "/" to make it work.
    `write` is handled specially, by making write() and create() calls.
    You can use `create` to insert new records.
    Otherwise, the model can have a custom method you could use.

    :param model: The model
    :param data: The list of rows (dict or list)
    :param method: The name of the method to call
    :param method_row_type: The type of the rows; dict (default) or list
    :param fields: List of field name for list rows
    :param formatter: The formatter to use
    :return: The result of the method call
    """
    log = logging.getLogger(__name__)

    if method == 'load':
        method_row_type = list
    elif method_row_type is None or method in ('create', 'write'):
        method_row_type = dict
    log.debug("Load: %s(), row type is %s", method, method_row_type)

    if formatter is None:
        formatter = Formatter(model)

    log.info("Load: convert and format data")
    if method_row_type == dict:
        data = __convert_to_type_dict(data, fields)
        data = [formatter.format_dict(d) for d in data]
    elif method_row_type == list:
        data, fields = __convert_to_type_list(data, fields)
        formatter_functions = [formatter.format_function[f] for f in fields]
        data = [[ff(v) for ff, v in zip(formatter_functions, d)] for d in data]
    else:
        raise Exception('Unsupported method row type: %s' % method_row_type)

    log.info("Load data using %s.%s(), %d records", model.model, method, len(data))
    if method == 'load':
        fields = [f.replace('.', '/') for f in cast(List[str], fields)]
        return model.execute(method, fields=fields, data=data)
    if method == 'write':
        return __load_data_write(model, data)
    if fields:
        return model.execute(method, data, fields=fields)
    return model.execute(method, data)


def __convert_to_type_list(
    data: Iterable, fields: Optional[List[str]]
) -> Tuple[Iterable[List], List[str]]:
    idata = iter(data)
    first_row = next(idata, None)
    if first_row is None:
        return [], fields or ['id']
    if not isinstance(first_row, list):
        if not fields:
            raise RuntimeError('Missing fields to convert into type list')
        data = ([d.get(f) for f in fields] for d in data)
    elif fields is None:
        logging.getLogger(__name__).debug("Load: using first row as field names")
        fields = first_row
        data = idata
    elif not isinstance(data, list):
        data = [first_row] + list(data)
    return data, fields


def __convert_to_type_dict(data: Iterable, fields: Optional[List[str]]) -> Iterable[Dict]:
    idata = iter(data)
    first_row = next(idata, None)
    if first_row is None:
        return []
    if isinstance(first_row, list):
        if fields is None:
            fields = first_row
            data = (dict(zip(fields, d)) for d in idata)
        else:
            if not isinstance(data, list):
                data = [first_row] + list(idata)
            if fields:
                data = ({f: d[i] for i, f in enumerate(fields)} for d in data)
    elif not isinstance(data, list):
        data = [first_row] + list(idata)
    return data


def __load_data_write(model: OdooModel, data: List[Dict]) -> Dict:
    """Use multiple write() and create() calls to update data

    :return: {'write_count': x, 'create_count': x, 'ids': [list of ids]}
    """
    create_data = []
    ids = []
    for d in data:
        id = d.pop('id')
        if id:
            model.execute('write', id, d)
            ids.append(id)
        else:
            create_data.append(d)
            ids.append(0)
    if create_data:
        created_ids = model.execute('create', create_data)
        iids = iter(created_ids)
        for i in range(len(ids)):
            if not ids[i]:
                ids[i] = next(iids)
        assert next(iids, None) is None
    return {
        'write_count': len(data) - len(create_data),
        'create_count': len(create_data),
        'ids': ids,
    }


@dataclass
class ColumnSpec:
    """Column specification for SQL tables"""

    name: str
    typ: str

    def __str__(self) -> str:
        return f"{self.name} {self.typ}"


@dataclass
class ExportData:
    """Exported data from Odoo"""

    schema: List[Dict]
    data: List[List]

    @property
    def column_names(self):
        return [h['name'] for h in self.schema]

    def to_dicts(self) -> Iterable[Dict]:
        """Return the data as dicts"""
        fields = self.column_names
        return (dict(zip(fields, d)) for d in self.data)

    def to_csv(self, with_header=True) -> Iterable[List[str]]:
        """Return the data for writing a csv file"""
        if with_header:
            yield self.column_names
        for d in self.data:
            yield [str(v) if v is not None else '' for v in d]

    def to_pandas(self, *, normalize_names: bool = True):
        """Create a pandas DataFrame"""
        import pandas

        columns = [c.name for c in self.get_sql_columns()] if normalize_names else self.column_names
        return pandas.DataFrame(self.data, columns=columns)

    def to_dbapi(self, con, table_name: str, *, only_data: bool = False, drop: bool = False):
        """Write the data to an SQL database

        :param con: The connection or transaction DBAPI (uses execute and executemany)
        :param table_name: The name of the table
        :param only_data: If True, only append data
        :param drop: If True, either drop the table or truncate it
        """
        colspecs = self.get_sql_columns()
        if not only_data:
            # create or replace table
            if drop:
                con.execute(f"drop table if exists {table_name}")
            con.execute(f"create table {table_name}({', '.join(str(cs) for cs in colspecs)})")
        elif drop:
            # truncate table
            con.execute(f"truncate table {table_name}")
        # insert data
        con.executemany(
            f"""insert into {table_name}
            ({', '.join(cs.name for cs in colspecs)})
            values (?{',?' * (len(colspecs) - 1)})
            """,
            self.data,
        )

    def get_sql_columns(self) -> List[ColumnSpec]:
        """Get the list of tuples (normalized_column_name, column_type) to write into a table"""
        type_to_sql = {
            'binary': 'binary',
            'boolean': 'boolean',
            'char': 'varchar',
            'selection': 'varchar',
            'date': 'date',
            'datetime': 'datetime',
            'float': 'float',
            'integer': 'integer',
            'many2many': 'varchar',
            'one2many': 'varchar',
            'many2one': 'int',
            'monetary': 'decimal(10, 2)',
        }
        return [
            ColumnSpec(
                name=info['name'].replace('.', '_').lower(),
                typ=type_to_sql.get(str(info.get('type')), 'varchar'),
            )
            for info in self.schema
        ]

    def __len__(self) -> int:
        return len(self.data)

    def __str__(self) -> str:
        return f"ExportData{self.column_names}({len(self.data)} rows)"


def fields_from_export(model: OdooModel, export_name: str) -> List[str]:
    """Return the list of fields in ir.exports"""
    fields = model.odoo['ir.exports.line'].search_read(
        [
            ('export_id.name', '=', export_name),
            ('export_id.resource', '=', model.model),
        ],
        ['name'],
    )
    fields = [f['name'].replace('/', '.') for f in fields]
    if not fields:
        raise ValueError('No fields to export')
    return fields


def domain_from_filter(model: OdooModel, filter_name: str) -> Dict:
    """Return a tuple (domain, kwargs for search) from a filter name"""
    filter_data = model.odoo['ir.filters'].search_read_dict(
        [
            ('name', '=', filter_name),
            ('model_id', '=', model.model),
        ],
        ['domain', 'context', 'sort'],
    )
    if not filter_data:
        raise ValueError('Filter not found')
    r = {'domain': filter_data['domain']}
    if filter_data.get('sort'):
        r['order'] = json.loads(filter_data.get('sort'))
    if filter_data.get('context'):
        r['context'] = json.loads(filter_data.get('context'))
    return r


def export_data(
    model: OdooModel,
    domain: List,
    fields: List[str],
    *,
    formatter: Optional[Formatter] = None,
    expand_many: bool = False,
) -> ExportData:
    """Export data into a tabular format

    :param model: Odoo model
    :param filter_or_domain: Either a domain TODO update desc
        or an ir.filters name
    :param export_or_fields: Either a list of fields (like is search_read_dict)
        or an ir.exports name
    :param formatter: The formatter to use to decode data
    :param expand_many: Flatten lists embedded in the result (default: False)
    :return: List of rows with data
    """
    log = logging.getLogger(__name__)

    if formatter is None:
        log.debug('Export: setup field decoder')
        formatter = Formatter(model)
        # fetch field types for related fields
        for field in fields:
            fparts = field.split('.')
            if formatter.get_type(field) or len(fparts) < 2:
                continue
            p_model = model
            for i, p in enumerate(fparts, 1):
                p_info = p_model.fields().get(p, {})
                p_model_name = p_info.get('relation')
                if not p_model_name:
                    break  # not found
                p_model = p_model.odoo[p_model_name]
                formatter.load_from_model(p_model, prefix='.'.join(fparts[:i]))
    field_infos = [{**formatter.field_info.get(field, {}), "name": field} for field in fields]

    log.info('Export: search and read data')
    records = model.search_read_dict(domain, fields)

    log.info('Export: cleaning data')
    data = list(flatten(records, fields, formatter=formatter, expand_many=expand_many))
    return ExportData(field_infos, data)


def add_fields(
    model: OdooModel, data: List[Dict], by_field: str, fields: List[str] = ['id'], domain: List = []
):
    """Add fields by querying the model

    :param model: The model
    :param data: The list of dicts
    :param by_field: The field name to use to find other fields
    :param fields: The fields to get (default: ['id'])
    :param domain: Additional domain to use
    :raises Exception: When multiple results have the same by_field key
    """
    domain_by_field: List[Any] = [(by_field, 'in', [d[by_field] for d in data])]
    domain = ['&'] + domain_by_field + (domain if domain else domain_by_field)
    fetched_data = model.search_read_dict(domain, fields + [by_field])
    index = {d.pop(by_field): d for d in fetched_data}
    if len(index) != len(fetched_data):
        raise Exception('%s is not unique in %s when adding fields' % (by_field, model.model))
    for d in data:
        updates = index.get(d[by_field])
        if updates:
            d.update(updates)
        else:
            d.update({f: None for f in fields})


def add_xml_id(model: OdooModel, data: List, *, id_name='id', xml_id_field='xml_id'):
    """Add a field containg the xml_id

    :param model: The model
    :param data: The list of dicts or rows (list to append to)
    :param id_name: The name of the field to get the resource ids (default: 'id')
    :param xml_id_field: The name of the xmlid field (default: 'xml_id')
    """
    if id_name != 'id':
        relation = model.fields()[id_name].get('relation')
        model = model.odoo.get_model(cast(str, relation), check=True)
    id_index: Optional[int] = None
    ids = set()
    for row_num, row in enumerate(data):
        if isinstance(row, dict):
            ids.add(row[id_name])
        elif isinstance(row, list):
            if row_num == 0:
                id_index = row.index(id_name)
            else:
                ids.add(row[cast(int, id_index)])
        else:
            raise TypeError('Cannot append the url to %s' % type(row))
    xml_ids = {
        i['res_id']: i['complete_name']
        for i in model.odoo['ir.model.data'].search_read(
            [('model', '=', model.model), ('res_id', 'in', list(ids))],
            ['complete_name', 'res_id'],
        )
    }
    if id_index is None:
        # we have dicts
        for row in data:
            row[xml_id_field] = xml_ids.get(row[id_name], False)
    else:
        # we have a list
        for row_num, row in enumerate(data):
            if row_num == 0:
                row.append(xml_id_field)
            else:
                row.append(xml_ids.get(row[id_index], False))


def add_url(
    model: OdooModel,
    data: List,
    *,
    url_field='url',
    model_id_func=None,
    build_url=lambda _r, model_name, id: f"/web#model={model_name}&id={id}",
):
    """Add an URL field to data

    :param model: The model
    :param data: The list of dicts or rows (list to append to)
    :param url_field: The name of the URL field (default: 'url')
    :param model_id_func: The function to get a tuple (model_name, id)
    :param build_url: Function to build the URL (record, model_name, id) -> "/web..."
    """
    base_url = model.odoo.url
    if not model_id_func and data:
        if isinstance(data[0], list):
            model_id_func = lambda r: (model.model, r[0])  # noqa: E731
        else:
            model_id_func = lambda d: (model.model, d['id'])  # noqa: E731
    for row_num, row in enumerate(data):
        model_name, id = model_id_func(row)
        url = build_url(row, model_name, id)
        if url:
            url = urljoin(base_url, url)
        if isinstance(row, dict):
            row[url_field] = url
        elif isinstance(row, list):
            if row_num == 0:
                row.append(url_field)
            else:
                row.append(url)
        else:
            raise TypeError('Cannot append the url to %s' % type(row))


def _flatten(value, access: List[str]) -> Any:
    if not access:
        return value
    if isinstance(value, dict):
        return _flatten(value.get(access[0]), access[1:])
    if isinstance(value, list):
        return [_flatten(i, access) for i in value]
    return False  # default


def _expand_many(data: Iterable[Dict]) -> Iterator[Dict]:
    for d in data:
        should_yield = True
        for k, v in d.items():
            if isinstance(v, list) and len(v):
                should_yield = False
                for i in v:
                    yield from _expand_many([{**d, k: i}])
        for k, v in d.items():
            if should_yield and isinstance(v, dict):
                should_yield = False
                for row in _expand_many([v]):
                    yield {**d, k: row}
        if should_yield:
            yield d


def flatten(
    data: Iterable[Dict],
    fields: List[str],
    *,
    formatter: Optional[Formatter] = None,
    expand_many: bool = False,
) -> Iterator[List]:
    """Flatten each dict with values into a single row"""
    if expand_many:
        data = _expand_many(data)
    field_levels = [f.split('.') for f in fields]
    result = ([_flatten(d, fl) for fl in field_levels] for d in data)
    if formatter is not None:
        decoders = [formatter.decode_function[f] for f in fields]
        result = ([dec(v) for dec, v in zip(decoders, r)] for r in result)
    return result


__all__ = [
    'Formatter',
    'make_batches',
    'load_data',
    'export_data',
    'add_fields',
    'add_url',
    'add_xml_id',
]
