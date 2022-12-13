from collections import namedtuple
from typing import NamedTuple, Dict, cast


class WrappedNamedTuple:
    """
    Regular NamedTuple doesn't allow names that begin with underscores.
    This object behaves like a named tuple, but allows underscores in the names.
    """

    def __init__(self, tuple_value: NamedTuple, name_mapping: Dict, dict_value: Dict):
        self.tuple_value = tuple_value
        self.name_mapping = name_mapping
        self.dict_value = dict_value

    def __eq__(self, other):
        return self.tuple_value == other

    def __getattr__(self, item):
        return getattr(self.tuple_value, self.name_mapping[item])

    def __getitem__(self, item):
        return self.tuple_value[item]

    def __iter__(self):
        return self.tuple_value.__iter__()

    def __str__(self):
        result = ", ".join(
            f"{name}={getattr(self.tuple_value, key)}"
            for name, key in self.name_mapping.items()
        )
        return f"WrappedNamedTuple({result})"

    def __repr__(self):
        return self.__str__()

    def _asdict(self):
        return {
            key: self.dict_value[new_key] for key, new_key in self.name_mapping.items()
        }

    @staticmethod
    def from_dict(result: dict) -> NamedTuple:
        fields = result.keys()
        named_tuple_class = namedtuple(
            field_names=fields,
            typename="Result",
            rename=True,
        )
        # pylint: disable=protected-access
        name_mapping = dict(zip(fields, named_tuple_class._fields))
        dict_value = {name_mapping[key]: value for key, value in result.items()}
        tuple_value = named_tuple_class(**dict_value)

        return cast(
            NamedTuple,
            WrappedNamedTuple(
                tuple_value=tuple_value,
                name_mapping=name_mapping,
                dict_value=dict_value,
            ),
        )  # We pretend Result is a named tuple
