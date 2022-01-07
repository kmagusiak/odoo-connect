import logging
from abc import ABC, abstractmethod

__doc__ = """
Base class for Odoo RPC.
"""


class OdooClientBase(ABC):
    """Odoo server connection"""

    def __init__(self, **kwargs):
        # XXX document kwargs for ipython
        """Create new connection and authenicate when username is given."""
        log = logging.getLogger(__name__)
        self.url = kwargs['url']
        self._database = kwargs['database']
        log.info(
            "Odoo connection (protocol: [%s]) initialized [%s], db: [%s]",
            self.protocol,
            self.url,
            self.database,
        )
        username = kwargs.get('username')
        if username:
            self.authenticate(username, kwargs.get('password'))
            log.info("Login successful [%s], [%s] uid: %d", self.url, self.username, self.uid)
        else:
            self.authenticate(None, None)

    def authenticate(self, username: str, password: str):
        """Authenticate"""
        self._username = username
        self._password = password
        if not username:
            self.uid = None
            return
        self.uid = self._call(
            "common",
            "authenticate",
            self._database,
            self._username,
            self._password,
        )
        if not self.uid:
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

    def ref(self, xml_id: str, raise_if_not_found=True):
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

    def version(self):
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
    def database(self) -> str:
        """Get database name"""
        return self._database

    def __getitem__(self, model: str) -> "OdooModel":
        """Alias for get_model"""
        return self.get_model(model)

    def __repr__(self):
        user = str(self.uid or self.username)
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

    def fields(self, fields=None):
        """Returns the fields of the model"""
        return self.execute(
            'fields_get',
            allfields=fields or [],
            attributes=['string', 'type', 'readonly', 'store', 'relation'],
        )

    def __getattr__(self, name):
        """By default, return function bound to exec(name, ...)"""

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
