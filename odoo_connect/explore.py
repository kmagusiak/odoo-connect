from typing import Any, Iterable


class Field:
    def __init__(self, model, *, name=None, parent: "Field" = None):
        self.__model = model
        self.__name = name
        self.__parent = parent

    def __dir__(self) -> Iterable[str]:
        return self.__model.fields().keys()

    def __getattr__(self, __name: str) -> Any:
        return self.__getitem__(__name)

    def __getitem__(self, __name: str) -> Any:
        prop = self.__model.fields().get(__name)
        if prop:
            relation = prop.get('relation')
            if relation:
                return Field(self.__model.odoo.get_model(relation), name=__name, parent=self)
            return Field(self.__model, name=__name, parent=self)
        return None

    def _properties(self, full=False):
        if not self.__name:
            raise Exception('No field selected')
        return self.__parent.__model.fields(full).get(self.__name)

    @property
    def _model(self):
        return self.__model

    def __repr__(self) -> str:
        return "FieldsOf" + repr(self.__model) + ('/name:' + self.__name if self.__name else '')

    def __str__(self) -> str:
        if not self.__name:
            return ''
        prefix = str(self.__parent or '')
        return prefix + ('.' if prefix else '') + self.__name

    # Domain builder

    def __eq__(self, value):
        return self.op('=', value)

    def __ne__(self, value):
        return self.op('!=', value)

    def __gt__(self, value):
        return self.op('>', value)

    def __ge__(self, value):
        return self.op('>=', value)

    def __lt__(self, value):
        return self.op('<', value)

    def __le__(self, value):
        return self.op('<=', value)

    def __in__(self, value):
        return self.op('in', value)

    def op(self, op, value):
        return Domain(self, op, value)


class Domain:
    def __init__(self, field, op, value) -> None:
        if isinstance(field, Domain):
            if value:
                self.domain = [op] + field.domain + value.domain
            else:
                self.domain = [op] + field.domain
        else:
            self.domain = [(str(field), op, value)]

    def __and__(self, other):
        return Domain(self, '&', other)

    def __or__(self, other):
        return Domain(self, '|', other)

    def __not__(self):
        return Domain(self, '!', False)

    def __repr__(self) -> str:
        return 'Domain:' + str(self.domain)

    def __str__(self) -> str:
        return str(self.domain)


GLOBAL_CACHE = {}


class Instance:
    def __init__(self, model, ids, fields) -> None:
        self.__model = model
        self.__fields = fields or Field(model)
        self.__ids = ids

    @property
    def fields(self):
        return self.__fields

    def __len__(self):
        return len(self.__ids)

    # TODO in

    def __dir__(self) -> Iterable[str]:
        return self.__fields.__dir__()

    def __getattr__(self, __name: str) -> Any:
        return self.__getitem__(__name)

    def __getitem__(self, __name: str) -> Any:
        value = self.mapped(__name, dots=False)
        if isinstance(value, list):
            if len(self.__ids) == 1:
                return value[0]
            if len(self.__ids) == 0:
                return False
            raise Exception('Too many values to unpack: ' + __name)
        return value

    def mapped(self, path: str, *, dots=True):
        if dots:
            paths = path.split('.', 1)
            if len(paths) == 2:
                value = self.mapped(paths[0], dots=False)
                return value.mapped(paths[1])
        field = self.__fields[path]
        prop = field._properties()
        if not prop:
            raise Exception('Invalid field: ' + path)
        relation = prop.get('relation')
        if relation:
            ids = set(i for d in self.read() for i in d[path] or [] if isinstance(i, int))
            return Instance(field._model, list(ids), fields=field)
        return [d[path] for d in self.read()]

    def read(self):
        model_cache = GLOBAL_CACHE.get(self.__model)
        if not model_cache:
            GLOBAL_CACHE[self.__model] = model_cache = {}
        missing_ids = set(self.__ids) - model_cache.keys()
        if missing_ids:
            model_cache.update({d['id']: d for d in self.__model.read(list(missing_ids), [])})
        return [model_cache[i] for i in self.__ids]

    def browse(self, *ids):
        return Instance(self.__model, ids, self.__fields)

    def search(self, domain, **kw):
        if isinstance(domain, Domain):
            domain = domain.domain
        data = {d['id']: d for d in self.__model.search_read(domain, [], **kw)}
        model_cache = GLOBAL_CACHE.get(self.__model)
        if not model_cache:
            GLOBAL_CACHE[self.__model] = model_cache = {}
        model_cache.update(data)
        return self.browse(list(data))

    def invalidate_cache(self, ids=None):
        model_cache = GLOBAL_CACHE.get(self.__model)
        if not model_cache:
            return
        if ids is None:
            model_cache.clear()
        else:
            for id in ids:
                model_cache.pop(id, default=None)

    def __repr__(self) -> str:
        return repr(self.__model) + str(self.__ids)


def explore(model):
    return Instance(model, [], None)


__all__ = ['explore']
