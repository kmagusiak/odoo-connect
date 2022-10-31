import logging
import random
import re
from typing import Any, Dict, List, Optional, Union

import requests

__doc__ = """
JSON-RPC class for Odoo RPC.
"""


def urljoin(base: str, *parts) -> str:
    """Simple URL joining"""
    if not parts:
        return base
    if base.endswith("/"):
        base = base[:-1]
    return "/".join([base] + [p.strip("/") for p in parts])


def get_month(value: str) -> int:
    """Get the month number from a month name"""
    month = value.lower()[:3]
    return {
        'jan': 1,
        'feb': 2,
        'mar': 3,
        'apr': 4,
        'may': 5,
        'jun': 6,
        'jul': 7,
        'aug': 8,
        'sep': 9,
        'oct': 10,
        'nov': 11,
        'dec': 12,
    }.get(month, 0)


class OdooServerError(RuntimeError):
    """Error returned by Odoo"""

    def get_data(self) -> Optional[dict]:
        """Get the data dictionnary for the error"""
        return next((a for a in self.args if isinstance(a, dict)), None)

    def get_remote_trace(self) -> Optional[str]:
        """Get the debug trace received from the remote server"""
        data = self.get_data() or {}
        dat = data.get('data') or {}
        return dat.get('debug')


class OdooClient:
    """Odoo server connection"""

    url: str
    _models: Dict[str, "OdooModel"]
    _version: Dict[str, Any]
    _database: str
    _username: str
    _password: str
    _uid: Optional[int]

    def __init__(
        self,
        *,
        url: str,
        database: Optional[str] = None,
        **_kwargs,
    ):
        """Create new connection."""
        self.url = url
        self._database = database or ''
        self._models = {}
        self._version = {}
        self._username = ''
        self._password = ''
        self._uid = None
        self._init_session()
        if not database:
            self._database = self._init_default_database()
        assert self._database
        logging.getLogger(__name__).info(
            "Odoo connection initialized [%s], db: [%s]",
            self.url,
            self.database,
        )

    def _init_session(self):
        """Initialize the session"""
        self.__json_url = urljoin(self.url, "jsonrpc")
        self.session = requests.Session()

    def _init_default_database(self) -> str:
        """Gets the default database from the server"""
        log = logging.getLogger(__name__)
        log.debug("Lookup the default database for [%s]", self.url)
        # Get the default
        try:
            db = self._call("db", "monodb")
            if isinstance(db, str) and db:
                return db
        except OdooServerError:
            pass
        # Try to list databases
        dbs = self.list_databases()
        if len(dbs) == 1:
            return dbs[0]
        # Fail
        raise OdooServerError('Cannot determine the database for [%s]' % self.url)

    def authenticate(self, username: str, password: str):
        """Authenticate with username and password"""
        log = logging.getLogger(__name__)
        old_username = self._username
        self._uid = None
        self._username = username
        self._password = password
        if not username:
            if old_username:
                log.info('Logged out [%s]' % self.url)
            return
        user_agent_env = {}  # type: ignore
        self._uid = self._call(
            "common",
            "authenticate",
            self._database,
            self._username,
            self._password,
            user_agent_env,
        )
        if not self._uid:
            raise OdooServerError('Failed to authenticate user %s' % username)
        log.info("Login successful [%s], [%s] uid: %d", self.url, self.username, self._uid)

    def _json_rpc(self, method: str, params: Any):
        """Make a jsonrpc call"""
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": random.randint(0, 1000000000),
        }
        resp = self.session.post(self.__json_url, json=data)
        resp.raise_for_status()
        reply = resp.json()
        if reply.get("error"):
            raise OdooServerError(reply["error"])
        return reply.get("result", None)

    def _call(self, service: str, method: str, *args):
        return self._json_rpc("call", {"service": service, "method": method, "args": args})

    def _execute_kw(self, model: str, method: str, *args, **kw):
        """Execute a method on a model"""
        if not self._uid:
            raise RuntimeError('You must authenticate first')
        return self._call(
            "object",
            "execute_kw",
            self._database,
            self._uid,
            self._password,
            model,
            method,
            args,
            kw,
        )

    def get_model(self, model_name: str, check: bool = False) -> "OdooModel":
        """Get a model instance

        :param model: Name of the model
        :param check: Check if the model exists (default: no), if doesn't exist, return None
        :return: Proxy for the model functions
        """
        model = self._models.get(model_name)
        if model is None:
            model = OdooModel(self, model_name)
            self._models[model_name] = model
        if check:
            try:
                # call any method to check if the call works
                # let's fetch the fields (which we probably will do anyways)
                model.fields()
            except:  # noqa: E722
                raise OdooServerError('Model %s not found' % model)
        return model

    def list_databases(self) -> List[str]:
        """Get the list of databases (may be disabled on the server and fail)"""
        return self._call("db", "list")

    def list_models(self) -> List[str]:
        """Get the list of known model names."""
        models = self.get_model('ir.model').search_read([], ['model'])
        return [m['model'] for m in models]

    def ref(
        self, xml_id: str, fields: List[str] = [], raise_if_not_found: bool = True
    ) -> Optional[Dict]:
        """Read the record corresponding to the given `xml_id`."""
        if '.' not in xml_id:
            raise ValueError('xml_id not valid')
        module, name = xml_id.split('.', 1)
        rec = self.get_model('ir.model.data').search_read(
            [('module', '=', module), ('name', '=', name)], ['id', 'model', 'res_id'], limit=1
        )

        if rec:
            rec = rec[0]
            model = self.get_model(rec.get('model'))
            to_return = model.read(rec.get('res_id'), fields)
            if to_return:
                return to_return[0]
        if raise_if_not_found:
            raise ValueError(
                'No record found for unique ID %s. It may have been deleted.' % (xml_id)
            )
        return {}

    def version(self) -> dict:
        """Get the version information from the server"""
        if self._version:
            return self._version
        self._version = self._call(
            "common",
            "version",
        )
        return self._version

    @property
    def major_version(self) -> int:
        return self.version()['server_version_info'][0]

    @property
    def protocol(self) -> str:
        """Get protocol used"""
        return "jsonrpc"

    def is_connected(self) -> bool:
        """Check if the authentication is done"""
        return self._uid is not None

    @property
    def username(self) -> str:
        """Get username"""
        return self._username

    @property
    def user(self) -> dict:
        """Get user information"""
        if not self.is_connected:
            return {}
        data = self.get_model('res.users').read(
            self._uid,
            [
                'login',
                'name',
                'groups_id',
                'partner_id',
                'login_date',
            ],
        )
        return data[0] if data else None

    @property
    def database(self) -> str:
        """Get database name"""
        return self._database

    @database.setter
    def database(self, database: str):
        if database is None:
            raise ValueError('Cannot set database: None')
        self.authenticate('', '')  # log out first
        self._database = database

    def __getitem__(self, model: str) -> "OdooModel":
        """Alias for get_model"""
        return self.get_model(model)

    def __repr__(self) -> str:
        user = str(self._uid or self._username)
        return f"OdooClient({self.url},{self.protocol},db:{self.database},user:{user})"


class OdooModel:
    """Odoo model (object) RPC functions"""

    def __init__(self, odoo: OdooClient, model: str):
        """Initialize the model instance.

        :param odoo: Odoo instance
        :param model: Name of the model
        """
        self.odoo = odoo
        self.model = model
        self._field_info = None

    def __getattr__(self, name: str):
        """By default, return function bound to execute(name, ...)"""

        def odoo_wrapper(*args, **kw):
            return self.execute(name, *args, **kw)

        return odoo_wrapper

    def execute(self, method: str, *args, **kw):
        """Execute an rpc method with arguments"""
        logging.getLogger(__name__).debug("Execute %s on %s", method, self.model)
        return self.odoo._execute_kw(
            self.model,
            method,
            *args,
            **kw,
        )

    def __repr__(self) -> str:
        return repr(self.odoo) + "/" + self.model

    def fields(self, extended=False) -> Dict[str, dict]:
        """Returns the fields of the model"""
        if not self._field_info or (extended and not self._field_info['id'].get('name')):
            attributes = (
                [] if extended else ['string', 'type', 'readonly', 'required', 'store', 'relation']
            )
            self._field_info = self.execute(
                'fields_get',
                allfields=[],
                attributes=attributes,
            )
        return self._field_info  # type: ignore

    def __prepare_dict_fields(self, fields: Union[List[str], Dict[str, Dict]]) -> Dict[str, Dict]:
        """Make sure fields is a dict representing the data to get"""
        if isinstance(fields, list):
            new_fields: Dict[str, Dict] = {}
            for field in fields:
                level = new_fields
                for f in field.split('.'):
                    if f not in level:
                        level[f] = {}
                    level = level[f]
            return new_fields
        if isinstance(fields, dict):
            new_fields = {}
            for k, v in fields.items():
                if isinstance(v, set):
                    v = list(v)
                if isinstance(v, list):
                    new_fields[k] = self.__prepare_dict_fields(v)
            if new_fields:
                new_fields.update({k: v for k, v in fields.items() if k not in new_fields})
                return new_fields
            return fields
        raise ValueError('Invalid fields parameter: %s' % fields)

    def __read_dict_date(self, data, fields):
        """Transform dates into ISO-like format"""
        for field in fields:
            mapper = None
            if field.endswith(':quarter'):
                regex = re.compile(r'Q(\d) (\d+)')

                def mapper(v, range):
                    m = v and regex.match(v)
                    return "%s-Q%d" % (m.group(2), int(m.group(1))) if m else v

            elif field.endswith(':month'):
                regex = re.compile(r'(\w+) (\d+)')

                def mapper(v, range):
                    m = v and regex.match(v)
                    return "%s-%02d" % (m.group(2), get_month(m.group(1))) if m else v

            elif field.endswith(':week'):
                regex = re.compile(r'W(\w+) (\d+)')

                def mapper(v, range):
                    m = v and regex.match(v)
                    return "%s-W%02d" % (m.group(2), int(m.group(1))) if m else v

            elif field.endswith(':day'):
                regex = re.compile(r'(\d+) (\w+) (\d+)')

                def mapper(v, range):
                    m = v and regex.match(v)
                    return (
                        "%s-%02d-%02d" % (m.group(3), get_month(m.group(2)), int(m.group(1)))
                        if m
                        else v
                    )

            elif field.endswith(':hour'):
                regex = re.compile(r'(\d+):00 (\d+) (\w+)')

                def mapper(v, range):
                    if not v:
                        return v
                    date = range.get('from')
                    return date if date else v

            if mapper:
                raw_field = field.split(':', 1)[0]
                has_range = self.odoo.major_version >= 15
                for d in data:
                    if has_range:
                        d_range = d['__range'].get(raw_field)
                    else:
                        # parse the domain to get the range
                        d_range = {}
                        for e in d['__domain']:
                            if isinstance(e, list) and len(e) == 3 and e[0] == raw_field:
                                if e[1] == ">=" and 'from' not in d_range:
                                    d_range['from'] = e[2]
                                elif e[1] == "<" and 'to' not in d_range:
                                    d_range['to'] = e[2]
                    d[field] = mapper(d[field], d_range)
        return data

    def __read_dict_recursive(self, data, fields):
        """For each field, read recursively the data"""
        if not fields:
            fields = {f: {} for f in self.fields()}
        for field_name, child_fields in fields.items():
            field_info = self.fields().get(field_name, {})
            model_name = field_info.get('relation')
            if not model_name:
                # not a reference field, skip it
                continue

            # simplify contents and get ids
            many = field_info.get('type') != 'many2one'
            ids = set()
            if many:
                for datum in data:
                    value = datum.get(field_name)
                    if isinstance(value, list):
                        ids.update(value)
                    else:
                        datum[field_name] = []
            else:
                for datum in data:
                    value = datum.get(field_name)
                    if isinstance(value, list):
                        assert len(value) == 2 and not isinstance(value[1], int)
                        datum[field_name] = value[0]
                        ids.add(value[0])
            if not ids or not (set(child_fields) - {'id'}):
                continue

            # read the data from children
            model = self.odoo.get_model(model_name)
            children_data = model.read(list(ids), list(child_fields))
            model.__read_dict_recursive(children_data, child_fields)
            children_data = {e['id']: e for e in children_data}

            # replace the data
            if many:
                for datum in data:
                    datum[field_name] = [
                        children_data.get(v) or {"id": v} for v in datum.get(field_name) or []
                    ]
            else:
                for datum in data:
                    v = datum.get(field_name)
                    datum[field_name] = (children_data.get(v) or {"id": v}) if v else {}

        return data

    def read_dict(
        self,
        ids: Union[List[int], int],
        fields: Union[List[str], Dict[str, Dict]],
    ):
        """Read with a dictionnary output and hierarchy view

        Example: model.search_read_dict([], ['partner_id.name', 'name'])

        :param domain: The domain for the search
        :param fields: A list of fields (may contain chains f1.f2)
                       or a dict containing fields to read {field: {child_fields...}}
        :param kwargs: Other arguments passed to search_read (limit, offet, orderby, etc.)
        :return: A list of found objects
        """
        single = False
        if isinstance(ids, int):
            ids = [ids]
            single = True
        fields = self.__prepare_dict_fields(fields)
        data = self.read(ids, list(fields))
        result = self.__read_dict_recursive(data, fields)
        return result[0] if single else result

    def search_read_dict(self, domain: List, fields: Union[List[str], Dict[str, Dict]], **kwargs):
        """Search read with a dictionnary output and hierarchy view

        Similar to `read_dict`.

        :param domain: The domain for the search
        :param fields: A list of fields (may contain chains f1.f2)
                       or a dict containing fields to read {field: {child_fields...}}
        :param kwargs: Other arguments passed to search_read (limit, offet, orderby, etc.)
        :return: A list of found objects
        """
        fields = self.__prepare_dict_fields(fields)
        data = self.search_read(domain, list(fields), **kwargs)
        return self.__read_dict_recursive(data, fields)

    def read_group_dict(self, domain, aggregates, groupby, **kwargs):
        """Search read groupped data

        :param domain: The domain for the search
        :param aggregates: The aggregates
        :param groupby: Fields to group by
        :return: A list of groupped date
        """
        groupby = self.__prepare_dict_fields(groupby)
        groupby_list = list(groupby)
        if not groupby_list:
            raise ValueError('Missing groupby values')
        kwargs['lazy'] = False
        data = self.read_group(domain, aggregates or ['id'], groupby_list, **kwargs)
        data = self.__read_dict_date(data, groupby_list)
        return self.__read_dict_recursive(data, groupby)
