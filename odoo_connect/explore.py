from typing import Any, Dict, Iterable, List, Union

from . import odoo_rpc

"""Cache of read values"""
GLOBAL_CACHE: Dict[odoo_rpc.OdooModel, Dict[int, Dict[str, Any]]] = {}


class Instance:
    """A proxy for an instance set"""

    __model: odoo_rpc.OdooModel
    __ids: List[int]

    def __init__(self, model: odoo_rpc.OdooModel, ids: List[int]) -> None:
        self.__model = model
        self.__ids = ids

    def __len__(self):
        return len(self.__ids)

    def __dir__(self) -> Iterable[str]:
        return self.__model.fields().keys()

    @property
    def ids(self):
        return self.__ids

    def __getitem__(self, item) -> "Instance":
        ids = self.__ids[item]
        if not isinstance(ids, Iterable):
            ids = [ids]
        return Instance(self.__model, ids)

    def __getattr__(self, __name: str) -> Any:
        value = self._mapped(__name)
        if isinstance(value, list):
            if len(self.__ids) == 1:
                return value[0]
            if len(self.__ids) == 0:
                return False
            raise Exception('Too many values to unpack: ' + __name)
        return value

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name.startswith('_Instance__'):
            return super().__setattr__(__name, __value)
        if isinstance(__value, Instance):
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
        return self.write({__name: __value})

    def mapped(self, path: str):
        """Map/read a field path"""
        paths = path.split('.', 1)
        if len(paths) > 1:
            value = self._mapped(paths[0])
            if not isinstance(value, Instance):
                raise Exception(f'{paths[0]} is not a relation')
            return value.mapped(paths[1])
        return self._mapped(path)

    def _mapped(self, field_name: str) -> Union["Instance", List[Any]]:
        """Map/read a field"""
        prop = self.__model.fields().get(field_name)
        if not prop:
            raise Exception(f'Invalid field: {field_name}')
        values = [d[field_name] for d in self.read(check_field=field_name)]
        relation = prop.get('relation')
        if relation:
            model = self.__model.odoo.get_model(relation)
            ids = set(i for v in values for i in v or [] if isinstance(i, int) and i)
            return Instance(model, list(ids))
        return values

    def read(self, *, check_field=None) -> List[Dict[str, Any]]:
        """Read the data"""
        fields = self._default_fields()
        model_cache = self.__cache()
        missing_ids = set(self.__ids) - model_cache.keys()
        if missing_ids:
            model_cache.update({d['id']: d for d in self.__model.read(list(missing_ids), fields)})
        if isinstance(check_field, str) and check_field not in fields:
            missing_ids = set(i for i in self.__ids if check_field not in model_cache[i])
            for d in self.__model.read(list(missing_ids), [check_field]) if missing_ids else []:
                model_cache[d['id']][check_field] = d[check_field]
        return [model_cache[i] for i in self.__ids]

    def _default_fields(self):
        data = self.__model.fields()
        return [f for f, prop in data.items() if '2many' not in (prop.get('type') or '')]

    def browse(self, *ids: int) -> "Instance":
        """Create an instance with the given ids"""
        return Instance(self.__model, list(ids))

    def exists(self) -> "Instance":
        """Return only existing records"""
        # re-read records to validate
        self.invalidate_cache(self.__ids)
        self.read()
        model_cache = self.__cache()
        ids = set(self.__ids) & model_cache.keys()
        return self.browse(*ids) if len(ids) < len(self.__ids) else self

    def search(self, domain: List, **kw) -> "Instance":
        """Search for an instance"""
        fields = self._default_fields()
        data = self.__model.search_read(domain, fields, **kw)
        model_cache = self.__cache()
        model_cache.update({d['id']: d for d in data})
        return Instance(self.__model, [d['id'] for d in data])

    def name_search(self, name: str, **kw) -> "Instance":
        """Search by name"""
        # search and return only the ids
        data = self.__model.name_search(name, **kw)
        return Instance(self.__model, [d[0] for d in data])

    def create(self, *values: Dict[str, Any]) -> "Instance":
        """Create multiple instances"""
        if not values:
            return self.browse()
        ids = self.__model.create(list(values))
        return self.browse(*ids)

    def write(self, values: Dict[str, Any]):
        """Update the values of the current instance"""
        if not values:
            return
        self.__model.write(self.__ids, values)
        self.invalidate_cache(self.__ids)

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

    def __repr__(self) -> str:
        return repr(self.__model) + str(self.__ids)


def explore(model: odoo_rpc.OdooModel) -> Instance:
    """Create an empty instance to explore"""
    return Instance(model, [])


__all__ = ['explore']
