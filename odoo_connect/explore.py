from typing import Any, Iterable


class Field:
    def __init__(self, model, *, name=None, parent=None):
        self.__model = model
        self.__name = name
        self.__parent = parent

    def __dir__(self) -> Iterable[str]:
        return self.__model.fields().keys()

    def __getattr__(self, __name: str) -> Any:
        prop = self.__model.fields().get(__name)
        if prop:
            relation = prop.get('relation')
            if relation:
                return Field(self.__model.odoo.get_model(relation), name=__name, parent=self)
            return Field(self.__model, name=__name, parent=self)
        return None

    def _properties(self, full=False):
        return self.__model.fields(full).get(self.__name)

    def __repr__(self) -> str:
        return "FieldsOf" + repr(self.__model) + ('/' + self.__name if self.__name else '')

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
