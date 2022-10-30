from typing import Any, Callable, Dict, Iterable, List, Union

import odoo_connect.format

from . import odoo_rpc

__doc__ = """Interact more easily with Odoo records."""


"""Cache of read values"""
GLOBAL_CACHE: Dict[odoo_rpc.OdooModel, Dict[int, Dict[str, Any]]] = {}


class Instance:
    """A proxy for an instance set"""

    __model: odoo_rpc.OdooModel
    __ids: List[int]

    def __init__(self, model: odoo_rpc.OdooModel, ids: List[int]) -> None:
        self.__model = model
        self.__ids = ids

    def __bool__(self) -> bool:
        return bool(self.__ids)

    def __len__(self):
        return len(self.__ids)

    def __dir__(self) -> Iterable[str]:
        return self.__model.fields().keys()

    def __add__(self, other) -> "Instance":
        if self.__model.model != other.__model.model or not isinstance(other, Instance):
            raise ValueError('Cannot combine different models')
        ids = self.__ids + other.__ids
        return Instance(self.__model, ids)

    def __sub__(self, other) -> "Instance":
        if self.__model.model != other.__model.model or not isinstance(other, Instance):
            raise ValueError('Cannot combine different models')
        otherset = set(other.__ids)
        ids = [i for i in self.__ids if i not in otherset]
        return Instance(self.__model, ids)

    def __or__(self, other) -> "Instance":
        if self.__model.model != other.__model.model or not isinstance(other, Instance):
            raise ValueError('Cannot combine different models')
        ids = self.__ids + (other - self).__ids
        return Instance(self.__model, ids)

    def __and__(self, other) -> "Instance":
        if self.__model.model != other.__model.model or not isinstance(other, Instance):
            raise ValueError('Cannot combine different models')
        otherset = set(other.__ids)
        ids = [i for i in self.__ids if i in otherset]
        return Instance(self.__model, ids)

    @property
    def ids(self) -> List[int]:
        return self.__ids

    @property
    def _model(self) -> odoo_rpc.OdooModel:
        return self.__model

    def _formatter(self) -> odoo_connect.format.Formatter:
        return odoo_connect.format.get_default_formatter(self._model)

    def __getitem__(self, item) -> "Instance":
        ids = self.__ids[item]
        if not isinstance(ids, Iterable):
            ids = [ids]
        return Instance(self.__model, ids)

    def __getattr__(self, __name: str) -> Any:
        value = self._mapped(__name)
        if isinstance(value, list):
            if len(self.__ids) == 1:
                # decode the value get getting the attribute
                return self._formatter().decode_function[__name](value[0])
            if len(self.__ids) == 0:
                return False
            raise ValueError('Too many values to unpack: ' + __name)
        return value

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name.startswith('_Instance__'):
            return super().__setattr__(__name, __value)
        format = True
        if isinstance(__value, Instance):
            format = False
            prop = self.__model.fields().get(__name) or {}
            if '2many' in (prop.get('type') or ''):
                if len(__value) == 0:
                    __value = [(5, 0, 0)]  # remove all
                else:
                    __value = [(6, 0, __value.ids)]  # replace all
            else:
                if len(__value) > 1:
                    raise ValueError('Cannot assign multiple values')
                if len(__value) == 1:
                    __value = __value.ids[0]
                else:
                    __value = False
        # format the value when writing a scalar
        return self.write({__name: __value}, format=format)

    def mapped(self, path: str):
        """Map/read a field path"""
        paths = path.split('.', 1)
        if len(paths) > 1:
            value = self._mapped(paths[0])
            if not isinstance(value, Instance):
                raise ValueError(f'{paths[0]} is not a relation')
            return value.mapped(paths[1])
        return self._mapped(path)

    def _mapped(self, field_name: str) -> Union["Instance", List[Any]]:
        """Map/read a field"""
        prop = self.__model.fields().get(field_name)
        if not prop:
            raise ValueError(f'Invalid field: {field_name}')
        values = [d[field_name] for d in self.read(check_fields=[field_name])]
        relation = prop.get('relation')
        if relation:
            model = self.__model.odoo.get_model(relation)
            # value is either list[int] (many) or list[tuple[int, str]|False] (one)
            ids = set(i for v in values for i in (v or []) if isinstance(i, int) and i)
            return Instance(model, list(ids))
        return values

    def cache(self, fields: List[str] = [], computed=False, exists=False) -> "Instance":
        """Cache the record fields and return self"""
        fieldset = set(self._default_fields(computed=computed) + fields)
        model_cache = self.__cache()
        # find missing ids, when missing in cache or field missing in cache
        # read all at once to have more consistency and avoid roundtrips
        missing_ids = set(i for i in self.__ids if fieldset - model_cache.get(i, {}).keys())
        # an exists() check is not needed because read() will return only existing rows
        if not missing_ids:
            return self
        for d in self.__model.read(list(missing_ids), list(fieldset)):
            id = d['id']
            if id in model_cache:
                model_cache[id].update(d)
            else:
                model_cache[id] = d
        return self

    def read(self, *, check_fields: List[str] = []) -> List[Dict[str, Any]]:
        """Read the data"""
        self.cache(fields=check_fields)
        model_cache = self.__cache()
        try:
            return [model_cache[i] for i in self.__ids]
        except KeyError as e:
            raise odoo_rpc.OdooServerError(f"Cannot read {self.__model.model}: {e}")

    def _default_fields(self, *, computed=False) -> List[str]:
        """List of fields to read by default"""
        data = self.__model.fields()
        return [
            f
            for f, prop in data.items()
            if '2many' not in (prop.get('type') or '')
            and prop.get('type') != 'binary'
            and (computed or f in ('id', 'display_name') or prop.get('store'))
        ]

    def fields_get(self, field_names=[]) -> Dict[str, Dict]:
        """Get the field information"""
        data = self.__model.fields()
        if field_names:
            data = {k: v for k, v in data.items() if k in field_names}
        return data

    def browse(self, *ids: int) -> "Instance":
        """Create an instance with the given ids"""
        return Instance(self.__model, list(ids))

    def exists(self) -> "Instance":
        """Return only existing records"""
        # re-read records to validate
        self.invalidate_cache(self.__ids)
        self.cache(computed=False, exists=True)
        model_cache = self.__cache()
        ids = set(self.__ids) & model_cache.keys()
        return self.browse(*ids) if len(ids) < len(self.__ids) else self

    def search(self, domain: List, **kw) -> "Instance":
        """Search for an instance"""
        fields = self._default_fields()
        data = self.__model.search_read(domain, fields, **kw)
        # add only new data, keep cache consistent
        model_cache = self.__cache()
        model_cache.update({d['id']: d for d in data if d['id'] not in model_cache})
        return Instance(self.__model, [d['id'] for d in data])

    def name_search(self, name: str, **kw) -> "Instance":
        """Search by name"""
        # search and return only the ids
        data = self.__model.name_search(name, **kw)
        return Instance(self.__model, [d[0] for d in data])

    def create(self, *values: Dict[str, Any], format: bool = False) -> "Instance":
        """Create multiple instances"""
        if not values:
            return self.browse()
        if format:
            formatter = self._formatter().format_dict
            value_list = [formatter(d) for d in values]
        else:
            value_list = list(values)
        ids = self.__model.create(value_list)
        return self.browse(*ids)

    def write(self, values: Dict[str, Any], format: bool = False):
        """Update the values of the current instance"""
        if not values:
            return
        if format:
            values = self._formatter().format_dict(values)
        self.__model.write(self.__ids, values)
        self.invalidate_cache(self.__ids)

    def unlink(self):
        """Remove the records from the database"""
        self.invalidate_cache(self.__ids)
        self.__model.unlink(self.__ids)

    def copy(self):
        """Copy the records in the database"""
        ids = self.__model.copy(self.__ids)
        return self.browse(*ids)

    def __cache(self) -> Dict[int, Dict[str, Any]]:
        model_cache = GLOBAL_CACHE.get(self.__model)
        if not model_cache:
            GLOBAL_CACHE[self.__model] = model_cache = {}
        return model_cache

    def invalidate_cache(self, ids=None):
        """Invalidate the cache for a set of ids or all the model"""
        model_cache = GLOBAL_CACHE.get(self.__model)
        if not model_cache:
            return
        if ids is None:
            model_cache.clear()
        else:
            for id in ids:
                model_cache.pop(id, None)

    def filtered(self, predicate: Callable[["Instance"], bool]) -> "Instance":
        """Filter the records"""

        def _predicate(i):
            return predicate(self.browse(i))

        self.cache(computed=False)
        ids = list(filter(_predicate, self.__ids))
        return Instance(self.__model, ids)

    def sorted(self, order: Callable[["Instance"], Any]) -> "Instance":
        """Sort the objects by a field"""

        def sorted_key(i):
            return order(self.browse(i))

        self.cache(computed=False)
        ids = sorted(self.__ids, key=sorted_key)
        return Instance(self.__model, ids)

    def get_attachments(self) -> "Instance":
        """Return ir.attachment linked to this instance"""
        return explore(self.__model.odoo['ir.attachment']).search(
            [
                ('res_model', '=', self.__model.model),
                ('res_id', 'in', self.__ids),
                ('id', '!=', 0),  # to get all res_field
            ]
        )

    def _call(self, method, *args, model_method=False, **kw):
        """Call a method on the model

        :param model_method: Whether to don't pass ids
        """
        if model_method:
            return self.__model.execute(method, *args, **kw)
        return self.__model.execute(method, self.ids, *args, **kw)

    def __repr__(self) -> str:
        return repr(self.__model) + str(self.__ids)


def explore(model: odoo_rpc.OdooModel) -> Instance:
    """Create an empty instance to explore"""
    return Instance(model, [])


__all__ = ['explore']
