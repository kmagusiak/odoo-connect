import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Set, Union

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
            raise RuntimeError('Failed to authenticate user %s' % username)

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
                model.default_get(['id'])
            except:  # noqa: E722
                # Return none if didn't verify
                return None
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
                attributes=['string', 'type', 'readonly', 'store', 'relation'],
            )
        return self._field_info

    def load(self, fields, data):
        """Load the data into the model"""
        # TODO provide example
        return self.execute("load", fields=fields, data=data)

    def export(self, fields, domain=None, format=None, token=None, **kwargs):
        pass  # TODO use /web/export/csv
        return self.search_read_dict(domain, fields, **kwargs)

    def get_report(self):
        pass  # TODO use /report/<converter>/<reportname>/<docids>

    def get_binary(self, id, field_name):
        pass  # TODO use /web/content/<string:model>/<int:id>/<string:field>
        pass  # TODO? use /web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>

    def search_read_dict(
        self, domain: List, fields: Union[List[str], Set[str], Dict[str, Set[str]]], **kwargs
    ):
        """Search read with a dictionnary output and hierarchy view

        Example: model.search_read_dict([], ['partner_id.name', 'name'])

        :param domain: The domain for the search
        :param fields: A list of fields (may contain chains f1.f2)
                       or a dict containing (field: [fields])
        :return: A list of found objects
        """

        def parse_fields(fields) -> Dict[str, Set[str]]:
            """Convert to dict field_name -> related names"""
            new_fields = defaultdict(set)
            for field in fields:
                f_split = field.split('.', 1)
                child = new_fields[f_split[0]]
                if len(f_split) > 1:
                    child.add(f_split[1])
            return new_fields

        if isinstance(fields, list | set):
            fields = parse_fields(fields)
        data = self.search_read(domain, list(fields), **kwargs)

        def get_related_ids() -> Dict[str, Set[int]]:
            """For each field, check its type and convert relations to ids,
            return a dict model -> set of ids
            """
            related = defaultdict(set)
            for field in fields:
                model_name = self.fields().get(field, {}).get('relation')
                if not model_name:
                    continue
                for datum in data:
                    value = datum.get(field)
                    if not isinstance(value, list):
                        continue
                    # update related with ids
                    if len(value) == 2 and not isinstance(value[1], int):
                        # x2one
                        datum[field] = value[0]
                        value = [value[0]]
                    related[model_name].update(value)
            return related

        related = get_related_ids()
        if not related:  # nothing to fetch, stop here
            return data

        # recursive search for each model
        related_data: Dict[str, Dict[int, Dict]] = {}
        for model_name, ids in related.items():
            rel_fields = set(
                d
                for field, deep_fields in fields.items()
                if self.fields().get(field, {}).get('relation') == model_name
                for d in deep_fields
            )
            if not rel_fields:
                continue
            model = self.odoo[model_name]
            # build domain and add active field if it's in the model
            # TODO replace with a read call
            domain = [('id', 'in', list(ids))]
            if 'active' in model.fields():
                domain += [('active', 'in', [True, False])]
            related_data[model_name] = {
                e['id']: e for e in model.search_read_dict(domain, rel_fields)
            }

        # replace in data
        for field, deep_field in fields.items():
            if not deep_field:
                continue
            deep_field = set(f.split('.', 1)[0] for f in deep_field)
            model_name = self.fields().get(field, {}).get('relation')
            related_model = related_data.get(model_name)

            def resolve(i: int):
                return {
                    k: v
                    for k, v in (related_model.get(i) or {'id': i}).items()
                    if k == 'id' or k in deep_field
                }

            for datum in data:
                value = datum[field]
                if isinstance(value, list):
                    datum[field] = [resolve(e) for e in value]
                elif value:
                    datum[field] = resolve(value)

        return data
