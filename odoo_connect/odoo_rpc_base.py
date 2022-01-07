import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List

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
            raise Exception('Failed to authenticate user %s' % username)

    @abstractmethod
    def _call(self, service: str, method: str, *args):
        """Execute a method on a service"""
        pass

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

    def get_model(self, model: str, check: bool = False) -> "OdooModel":
        """Get a model instance

        :param model: Name of the model
        :param check: Check if the model exists (default: no), if doesn't exist, return None
        :return: Proxy for the model functions
        """
        model = OdooModel(self, model)
        if check:
            try:
                # call any method to check if the call works
                model.default_get(['id'])
            except:  # noqa: E722  pylint: disable=W0702
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

    def ref(self, xml_id: str, raise_if_not_found: bool = True) -> dict:
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
            to_return = model.search_read([('id', '=', rec.get('res_id'))], [])
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
        return self.get_model('res.users').read(
            self._uid,
            [
                'login',
                'name',
                'groups_id',
                'partner_id',
                'login_date',
            ],
        )

    @property
    def database(self) -> str:
        """Get database name"""
        return self._database

    def __getitem__(self, model: str) -> "OdooModel":
        """Alias for get_model"""
        return self.get_model(model)

    def __repr__(self):
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

    def __getattr__(self, name):
        """By default, return function bound to execute(name, ...)"""

        def odoo_wrapper(*args, **kw):
            return self.execute(name, *args, **kw)

        return odoo_wrapper

    def execute(self, method, *args, **kw):
        """Execute an rpc method with arguments"""
        logging.getLogger(__name__).debug("Execute %s on %s", method, self.model)
        return self.odoo._execute_kw(
            self.model,
            method,
            *args,
            **kw,
        )

    def __repr__(self):
        return repr(self.odoo) + "/" + self.model

    def fields(self, fields=None) -> List[dict]:
        """Returns the fields of the model"""
        return self.execute(
            'fields_get',
            allfields=fields or [],
            attributes=['string', 'type', 'readonly', 'store', 'relation'],
        )

    def load(self, fields, data):
        """Load the data into the model"""
        # TODO provide example
        return self.execute("load", fields=fields, data=data)

    def export(self, fields, domain=None, format=None, token=None, **kwargs):
        pass  # TODO use /web/export/csv
        return self.search_read_deep(domain, fields, **kwargs)

    def get_report(self):
        pass  # TODO use /report/<converter>/<reportname>/<docids>

    def get_binary(self, id, field_name):
        pass  # TODO use /web/content/<string:model>/<int:id>/<string:field>
        pass  # TODO? use /web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>

    def search_read_deep(self, domain, fields, **kwargs):  # TODO need?
        """Search read with chained fields

        Example: model.search_read_deep([], ['partner_id.name', 'name'])

        :param domain: The domain for the search
        :param fields: A list of fields (may contain chains) or a dict containing (field: [fields])
        :return: A list of found objects
        """

        def prepare_field_arguments(fields):
            if isinstance(fields, list):
                new_fields = defaultdict(list)
                for field in fields:
                    f_split = field.split('.', 1)
                    child = new_fields[f_split[0]]
                    if len(f_split) > 1:
                        child.append(f_split[1])
                fields = new_fields
            fields_data = self.fields(list(fields))
            deep_fields = {f: fields[f] for f, p in fields_data.items() if p.get('relation')}
            return fields_data, deep_fields

        def get_related_ids(data):
            related = defaultdict(set)
            for datum in data:
                for field, value in datum.items():
                    if not isinstance(value, list):
                        continue
                    model_name = fields_data[field].get('relation')
                    if len(value) == 2 and not isinstance(value[1], int):
                        # x2one
                        related[model_name].add(value[0])
                        datum[field] = value[0]
                    else:
                        # x2many
                        related[model_name].update(value)
            return related

        def replace_related_data(related, deep_fields, data):
            related_data = {}
            for model_name, ids in related.items():
                rel_fields = set()
                for field, deep in deep_fields.items():
                    if fields_data[field].get('relation') != model_name:
                        continue
                    rel_fields.update(deep)
                if not rel_fields:
                    continue
                rel_fields = list(rel_fields)
                rel = self.odoo[model_name].search_read_deep([('id', 'in', list(ids))], rel_fields)
                rel = {e['id']: e for e in rel}
                related_data[model_name] = rel
            # replace
            for datum in data:
                for field, value in datum.items():
                    deep_field = deep_fields.get(field)
                    if not deep_field or not value:
                        continue
                    related_model = related_data.get(fields_data[field]['relation'], {})

                    def resolve(i):
                        return {
                            k: v
                            for k, v in (related_model.get(i) or {'id': i}).items()
                            if k == 'id' or k in deep_field
                        }

                    if isinstance(value, list):
                        datum[field] = [resolve(e) for e in value]
                    elif isinstance(value, int):
                        datum[field] = resolve(value)

        fields_data, deep_fields = prepare_field_arguments(fields)
        data = self.search_read(domain, list(fields_data), **kwargs)
        related = get_related_ids(data)
        if not related:  # nothing to fetch, stop here
            return data
        replace_related_data(related, deep_fields, data)
        return data
