import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Union

__doc__ = """
Base class for Odoo RPC.
"""


def urljoin(base, *parts):
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

    pass


class OdooClientBase(ABC):
    """Odoo server connection"""

    url: str
    _models: Dict[str, "OdooModel"]

    def __init__(self, *, url, database, username=None, password=None, **_kwargs):
        """Create new connection and authenicate when username is given."""
        log = logging.getLogger(__name__)
        self.url = url
        self._database = database
        log.info(
            "Odoo connection (protocol: [%s]) initialized [%s], db: [%s]",
            self.protocol,
            self.url,
            self.database,
        )
        if username:
            self.authenticate(username, password)
            log.info("Login successful [%s], [%s] uid: %d", self.url, self.username, self._uid)
        else:
            self.authenticate(None, None)
        self._models = {}

    def authenticate(self, username: str, password: str):
        """Authenticate with username and password"""
        self._username = username
        self._password = password
        if not username:
            self._uid = None
            return
        user_agent_env = {}
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

    @abstractmethod
    def _call(self, service: str, method: str, *args):
        """Execute a method on a service"""
        raise NotImplementedError

    def _execute_kw(self, model: str, method: str, *args, **kw):
        """Execute a method on a model"""
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

    def ref(self, xml_id: str, fields: List[str] = [], raise_if_not_found: bool = True) -> dict:
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
        return False

    def version(self) -> dict:
        """Get the version information from the server"""
        return self._call(
            "common",
            "version",
        )

    @property
    @abstractmethod
    def protocol(self) -> str:
        """Get protocol used"""
        return "unknown"

    def is_connected(self) -> bool:
        """Check if we are connected"""
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

    def __getitem__(self, model: str) -> "OdooModel":
        """Alias for get_model"""
        return self.get_model(model)

    def __repr__(self) -> str:
        user = str(self._uid or self._username)
        return f"OdooClient({self.url},{self.protocol},db:{self.database},user:{user})"


class OdooModel:
    """Odoo model (object) RPC functions"""

    def __init__(self, odoo: OdooClientBase, model: str):
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

    def fields(self) -> Dict[str, dict]:
        """Returns the fields of the model"""
        if not self._field_info:
            self._field_info = self.execute(
                'fields_get',
                allfields=[],
                attributes=['string', 'type', 'readonly', 'required', 'store', 'relation'],
            )
        return self._field_info

    def __prepare_dict_fields(self, fields: Union[List[str], Dict[str, Dict]]) -> Dict[str, Dict]:
        """Make sure fields is a dict representing the data to get"""
        if isinstance(fields, list):
            new_fields = {}
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
                    return range.get('from') or v

            if mapper:
                raw_field = field.split(':', 1)[0]
                for d in data:
                    d[field] = mapper(d[field], d['__range'][raw_field])
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
        single = isinstance(ids, int)
        if single:
            ids = [ids]
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
