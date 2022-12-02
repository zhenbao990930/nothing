from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, Set, List, Union


@dataclass(frozen=True)
class UnknownType:
    """
    Represents a type that was used in type definition, but is not (yet) known.
    """

    name: str

    def resolve(self, resolved_types: Dict[str, KnownType]) -> KnownType:
        return resolved_types[self.name]


class KnownType(ABC):
    def resolve(self, resolved_types: Dict[str, KnownType]) -> KnownType:
        if self.is_resolved:
            return self

        return self._resolve(resolved_types)

    @cached_property
    def unknown_dependencies(self) -> Set[UnknownType]:
        deps = self.dependencies()
        directly_unknown = [t for t in deps if isinstance(t, UnknownType)]
        transitive_unknown = [
            unknown_dependency
            for t in deps
            for unknown_dependency in t.unknown_dependencies
            if isinstance(t, KnownType)
        ]
        return set(*directly_unknown, *transitive_unknown)

    @property
    def is_resolved(self) -> bool:
        """
        Type that is resolved is one that doesn't have any unknown dependencies in the subtree.
        """
        return bool(self.unknown_dependencies)

    @abstractmethod
    def dependencies(self) -> List[CairoType]:
        pass

    @abstractmethod
    def _resolve(self, resolved_types: Dict[str, KnownType]) -> KnownType:
        pass


CairoType = Union[UnknownType, KnownType]


@dataclass(frozen=True)
class FeltType(KnownType):
    def _resolve(self, resolved_types: Dict[str, KnownType]) -> KnownType:
        # Felt is already resolved
        pass

    def dependencies(self) -> List[CairoType]:
        return []


@dataclass(frozen=True)
class TupleType(KnownType):
    types: List[CairoType]

    def dependencies(self) -> List[CairoType]:
        return self.types

    def _resolve(self, resolved_types: Dict[str, KnownType]) -> TupleType:
        return TupleType([t.resolve(resolved_types) for t in self.types])


@dataclass(frozen=True)
class NamedTupleTuple(KnownType):
    types: OrderedDict[str, CairoType]

    def dependencies(self) -> List[CairoType]:
        return self.types.values()

    def _resolve(self, resolved_types: Dict[str, KnownType]) -> NamedTupleTuple:
        return NamedTupleTuple(
            OrderedDict(
                (name, t.resolve(resolved_types)) for name, t in self.types.items()
            )
        )


@dataclass(frozen=True)
class ArrayType(KnownType):
    inner_type: CairoType

    def dependencies(self) -> List[CairoType]:
        return [self.inner_type]

    def _resolve(self, resolved_types: Dict[str, KnownType]) -> ArrayType:
        return ArrayType(self.inner_type.resolve(resolved_types))


@dataclass(frozen=True)
class StructType(KnownType):
    name: str
    # We need ordered dict, because it is important in serialization
    types: OrderedDict[str, CairoType]

    def dependencies(self) -> List[CairoType]:
        return self.types.values()

    def _resolve(self, resolved_types: Dict[str, KnownType]) -> StructType:
        return StructType(
            self.name,
            OrderedDict(
                (name, t.resolve(resolved_types)) for name, t in self.types.items()
            ),
        )


# Inline type it one that can be used inline. For instance (a: felt, b: felt*, c: (felt, felt)).
InlineType = Union[UnknownType, FeltType, ArrayType, TupleType, NamedTupleTuple]
