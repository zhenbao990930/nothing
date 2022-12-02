from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List

from starknet_py.cairo.type_parser import TypeParser
from starknet_py.cairo.data_types import StructType, KnownType
from starknet_py.utils.abi._structure_resolver import StructureResolver
from starknet_py.utils.abi.abi_shape import (
    StructDict,
    AbiDictList,
    FunctionDict,
    TypedMemberDict,
    EventDict,
)


@dataclass
class Abi:
    @dataclass
    class Function:
        name: str
        inputs: OrderedDict[str, KnownType]
        outputs: OrderedDict[str, KnownType]

    @dataclass
    class Event:
        name: str
        data: OrderedDict[str, KnownType]

    defined_structures: Dict[str, StructType]
    functions: Dict[str, Function]
    events: Dict[str, Event]

    @staticmethod
    def from_dict(abi: AbiDictList) -> Abi:
        structures = StructureResolver(
            Abi._parse_abi_struct(entry) for entry in abi if entry["type"] == "struct"
        ).resolve()
        type_parser = TypeParser(structures)
        functions = {
            entry["name"]: Abi._parse_abi_function(entry, type_parser)
            for entry in abi
            if entry["type"] == "function"
        }
        events = {
            entry["name"]: Abi._parse_event(entry, type_parser)
            for entry in abi
            if entry["type"] == "event"
        }
        return Abi(defined_structures=structures, functions=functions, events=events)

    @staticmethod
    def _parse_abi_struct(struct: StructDict) -> StructType:
        ordered_members = sorted(struct["members"], key=lambda m: m["offset"])
        members = OrderedDict()
        for member in ordered_members:
            name = member["name"]
            if name in members:
                raise ValueError(
                    f"Field [{member}] is defined more than once in ABI of structure [{struct['name']}]."
                )

            member_type = TypeParser().parse_inline_type(member["type"])
            members[name] = member_type
        return StructType(struct["name"], members)

    @staticmethod
    def _parse_abi_function(
        function: FunctionDict, type_parser: TypeParser
    ) -> Abi.Function:
        return Abi.Function(
            name=function["name"],
            inputs=Abi._parse_members(
                function["name"], function["inputs"], type_parser
            ),
            outputs=Abi._parse_members(
                function["name"], function["outputs"], type_parser
            ),
        )

    @staticmethod
    def _parse_event(event: EventDict, type_parser: TypeParser) -> Abi.Event:
        return Abi.Event(
            name=event["name"],
            data=Abi._parse_members(event["name"], event["data"], type_parser),
        )

    @staticmethod
    def _parse_members(
        entity_name: str, params: List[TypedMemberDict], parser: TypeParser
    ) -> OrderedDict[str, KnownType]:
        members = OrderedDict()
        for param in params:
            name = param["name"]
            if name in members:
                raise ValueError(
                    f"Parameter [{name}] is defined more than once in ABI of [{entity_name}]."
                )

            members[name] = parser.parse_inline_type(param["type"])

        return members
