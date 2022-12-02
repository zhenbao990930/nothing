from __future__ import annotations
from collections import defaultdict
from typing import List, Dict, DefaultDict, Iterable

from starknet_py.cairo.data_types import StructType


class StructureResolver:
    """
    Utility class for resolving unknown types in structures. It is needed because ABI doesn't provide any order for
    parsing structures. This means that during parsing some referred types are not known yet.
    """

    structs: Dict[str, StructType]

    def __init__(self, structs_seq: Iterable[StructType]):
        structs: Dict[str, StructType] = {}
        for struct in structs_seq:
            if struct.name in structs:
                raise ValueError(f"Structure [{struct.name}] is defined more than once")

            structs[struct.name] = struct

        self.structs = structs

    def resolve(self) -> Dict[str, StructType]:
        """
        Resolve struct dependencies using topological sort.
        """
        unresolved_dependencies_left: Dict[str, int] = {}
        dependant_on: DefaultDict[str, List[str]] = defaultdict(list)
        resolvable_types: List[str] = []

        for name, struct in self.structs.items():
            # There has to be at least one type like this, otherwise there is a cycle (checked later).
            if struct.is_resolved:
                resolvable_types.append(name)
                continue

            unresolved_dependencies_left[name] = len(struct.unknown_dependencies)
            # Save this struct in "waiting list" for each dependency
            for dependency in struct.unknown_dependencies:
                self._assert_dependency_exists(name, dependency.name)
                dependant_on[dependency.name].append(name)

        resolved: Dict[str, StructType] = {}
        while resolvable_types:
            struct_name = resolvable_types.pop()
            # Resolve this struct and add it to our dictionary.
            # Algorithm ensures we won't resolve struct that depends on something that is not resolved.
            resolved[struct_name] = self.structs[struct_name].resolve(resolved)

            for dependent in dependant_on[struct_name]:
                unresolved_dependencies_left[dependent] -= 1
                if unresolved_dependencies_left[dependent] == 0:
                    # No more missing dependencies, type can be resolved now
                    resolvable_types.append(dependent)

        self._assert_no_cycle(resolved)
        return resolved

    def _assert_dependency_exists(self, struct_name: str, dep_name: str):
        if struct_name not in self.structs:
            raise ValueError(
                f"Structure [{struct_name}] depends on type [{dep_name}] that is not defined"
            )

    def _assert_no_cycle(self, resolved: Dict[str, StructType]):
        if len(resolved) != len(self.structs):
            unresolved_types = set(self.structs.keys()).difference(resolved.keys())
            raise ValueError(
                f"Cycle detected, could not resolve types [{', '.join(unresolved_types)}]"
            )
