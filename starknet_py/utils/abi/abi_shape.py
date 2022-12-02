from typing import TypedDict, Literal, List, Union


class TypedMemberDict(TypedDict):
    name: str
    type: str


class StructMemberDict(TypedMemberDict):
    offset: int


class StructDict(TypedDict):
    name: str
    type: Literal["struct"]
    size: int
    members: List[StructMemberDict]


class FunctionDict(TypedDict):
    name: str
    type: Literal["function"]
    inputs: List[TypedMemberDict]
    outputs: List[TypedMemberDict]


class EventDict(TypedDict):
    name: str
    type: Literal["event"]
    data: List[TypedMemberDict]


AbiDictEntry = Union[StructDict, FunctionDict, EventDict]
AbiDictList = List[AbiDictEntry]
