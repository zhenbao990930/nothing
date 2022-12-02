from collections import defaultdict, OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Generic,
    TypeVar,
    List,
    Union,
    Tuple,
    Dict,
    DefaultDict,
    NamedTuple,
)

from abc import ABC, abstractmethod

from starkware.cairo.lang.compiler.ast.cairo_types import (
    TypeFelt,
    CairoType,
    TypePointer,
    TypeIdentifier,
    TypeTuple,
)

from starknet_py.cairo._type_parser import parse_abi_struct
from starknet_py.utils.data_transformer.cairo_types import StructType
from starknet_py.utils.data_transformer.data_transformer import construct_result_object
from starknet_py.utils.data_transformer.errors import (
    InvalidTypeException,
    InvalidValueException,
)

from starknet_py.cairo.felt import (
    encode_shortstring,
    cairo_vm_range_check,
    uint256_range_check,
)
from starknet_py.utils.abi.json_shape import StructDict, Abi

CairoData = List[int]


class CairoDataReader:
    data: List[int]
    position: int

    def __init__(self, input: List[int]):
        self.data = input
        self.position = 0

    @property
    def remaining_len(self) -> int:
        return len(self.data) - self.position

    def consume(self, size: int) -> CairoData:
        if size > self.remaining_len:
            raise ValueError(
                f"Requested {size} elements, {self.remaining_len} available."
            )
        slice = self.data[self.position : self.position + size]
        self.position += size
        return slice


class TransformContext:
    reader: CairoDataReader
    namespace_stack: List[str]

    @contextmanager
    def nest(self, name: str):
        self.namespace_stack.append(name)
        try:
            yield
        except InvalidTypeException as e:
            full_name = "".join(self.namespace_stack)
            # TODO
            raise InvalidTypeException(f"Error at [{full_name}]. {e}")
        finally:
            self.namespace_stack.pop()


AcceptedPythonType = TypeVar("AcceptedPythonType")
CanonicalPythonType = TypeVar("CanonicalPythonType")


class Transformer(ABC, Generic[AcceptedPythonType, CanonicalPythonType]):
    @abstractmethod
    def to_python(self, context: TransformContext) -> CanonicalPythonType:
        pass

    @abstractmethod
    def from_python(
        self, context: TransformContext, value: AcceptedPythonType
    ) -> CairoData:
        pass


# Just an integer or short string
TransformableToFelt = Union[int, str]


class FeltTransformer(Transformer[TransformableToFelt, int]):
    def to_python(self, context: TransformContext) -> int:
        [val] = context.reader.consume(1)
        cairo_vm_range_check(val)
        return val

    def from_python(self, context, value: TransformableToFelt) -> CairoData:
        if isinstance(value, str):
            value = encode_shortstring(value)
            return [value]

        if not isinstance(value, int):
            # TODO
            raise InvalidTypeException(f"should be int.")

        cairo_vm_range_check(value)
        return [value]


class Uint256Transformer(Transformer[int, int]):
    def to_python(self, context: TransformContext) -> int:
        [low, high] = context.reader.consume(2)
        value = (high << 128) + low
        uint256_range_check(value)
        return value

    def from_python(self, context, value: int) -> CairoData:
        uint256_range_check(value)
        return [value % 2**128, value // 2**128]


@dataclass
class TupleTransformer(Transformer[Union, Tuple]):
    types: List[Transformer]

    def to_python(self, context: TransformContext) -> Tuple:
        result = []

        for index, transformer in enumerate(self.types):
            with context.nest(f"[{index}]"):
                transformed = transformer.to_python(context)
                result.append(transformed)

        return tuple(*result)

    def from_python(self, context: TransformContext, value: Tuple) -> CairoData:
        if len(value) != len(self.types):
            # TODO
            raise InvalidValueException(
                f"Length mismatch: {len(value)} != {len(self.types)}."
            )

        result = []
        for index, transformer in enumerate(self.types):
            with context.nest(f"[{index}]"):
                transformed = transformer.from_python(context, value[index])
                result.extend(transformed)

        return result


@dataclass
class NamedTupleTransformer(Transformer[Union[Tuple, NamedTuple], NamedTuple]):
    types: OrderedDict[str, Transformer]

    def to_python(self, context: TransformContext) -> NamedTuple:
        result = {}

        for name, transformer in self.types.items():
            with context.nest(f"[{name}]"):
                result[name] = transformer.to_python(context)

        return construct_result_object(result)

    def from_python(self, context: TransformContext, value: Tuple) -> CairoData:
        if not isinstance(value, dict) and not NamedTupleTransformer.is_namedtuple(
            value
        ):
            # TODO
            raise InvalidValueException(f"must be dict or NamedTuple")

        # noinspection PyUnresolvedReferences, PyProtectedMember
        values: Dict = value if isinstance(value, dict) else value._asdict()

        result = []
        for name, transformer in self.types.items():
            with context.nest(f"[{name}]"):
                transformed = transformer.from_python(context, values[name])
                result.extend(transformed)

        return result

    @staticmethod
    def is_namedtuple(value) -> bool:
        return isinstance(value, tuple) and hasattr(value, "_fields")


@dataclass
class ArrayTransformer(Transformer[List, List]):
    inner_transformer: Transformer

    def to_python(self, context: TransformContext) -> List:
        result = []

        with context.nest(f".len"):
            [size] = context.reader.consume(1)

        for index in range(size):
            with context.nest(f"[{index}]"):
                transformed = self.inner_transformer.to_python(context)
                result.append(transformed)

        return result

    def from_python(self, context: TransformContext, value: List) -> CairoData:
        result = [len(value)]
        for index, value in enumerate(List):
            with context.nest(f"[{index}]"):
                transformed = self.inner_transformer.from_python(context, value[index])
                result.extend(transformed)

        return result


# Uint256 are structs as well, we return them as integers
StructTransformerResult = Union[Dict, int]


@dataclass
class StructTransformer(Transformer[Dict, Dict]):
    transformers: Dict[str, Transformer]

    def to_python(self, context: TransformContext) -> Dict:
        result = {}

        for key, transformer in self.transformers.items():
            with context.nest(f"[{key}]"):
                transformed = transformer.to_python(context)
                result[key] = transformed

        return result

    def from_python(self, context: TransformContext, value: Dict) -> CairoData:
        result = []

        for key, transformer in self.transformers.items():
            with context.nest(f"[{key}]"):
                if key not in value:
                    raise InvalidValueException(f"not provided.")

                transformed = transformer.from_python(context, value[key])
                result.extend(transformed)

        return result


uint256_type = StructType(
    "Uint256",
    OrderedDict[str, CairoType](
        [
            ("low", TypeFelt()),
            ("high", TypeFelt()),
        ]
    ),
)


@dataclass
class StructureRepository:
    transformers: Dict[str, Transformer]

    def __init__(self, abi: Abi):
        structs_list: List[StructDict] = [
            entry for entry in abi if entry["type"] == "struct"
        ]
        transformers = {"felt": FeltTransformer()}
        structs: Dict[str, StructType] = {}
        dependant_on: DefaultDict[str, List[str]] = defaultdict(list)
        unresolved_dependencies_left: Dict[str, int] = {}
        resolvable_structs: List[str] = []
        resolved: Dict[str, Transformer] = {}

        for struct in structs_list:
            name = struct["name"]
            if name in transformers:
                # TODO custom error
                raise ValueError(f"Structure [{name}] is defined more than once")

            parsed = parse_abi_struct(struct)
            structs[name] = parsed
            unresolved_dependencies_left[name] = len(parsed.unknown_dependencies)

            for dependency in parsed.unknown_dependencies:
                dependant_on[dependency].append(parsed.name)

            if not parsed.unknown_dependencies:
                resolvable_structs.append(name)

        while resolvable_structs:
            struct_name = resolvable_structs.pop()
            resolved[struct_name] = StructureRepository._resolve_struct(
                structs[struct_name], resolved
            )

            for dependent in dependant_on[struct_name]:
                unresolved_dependencies_left[dependent] -= 1
                if unresolved_dependencies_left[dependent] == 0:
                    resolvable_structs.append(dependent)

        if len(resolved) != len(structs):
            # TODO: Handle
            pass

    @staticmethod
    def _resolve_struct(
        parsed: StructType, resolved: Dict[str, Transformer]
    ) -> Transformer:
        # The only special case: uint256 is represented as structure {low, high}
        if StructureRepository._is_uint256_struct(parsed):
            return Uint256Transformer()

        return StructTransformer(
            {
                name: StructureRepository._resolve(type, resolved)
                for name, type in parsed.types
            }
        )

    @staticmethod
    def _is_uint256_struct(parsed: StructType) -> bool:
        return parsed == uint256_type

    @staticmethod
    def _resolve(type: CairoType, resolved: Dict[str, Transformer]) -> Transformer:
        if isinstance(type, TypeFelt):
            return FeltTransformer()
        if isinstance(type, TypePointer):
            return ArrayTransformer(
                StructureRepository._resolve(type.pointee, resolved)
            )
        if isinstance(type, TypeIdentifier):
            return resolved[str(type.name)]
        if isinstance(type, TypeTuple):
            if type.is_named:
                # OrderedDict outside refers only to the type
                from collections import OrderedDict

                return NamedTupleTransformer(
                    OrderedDict(
                        [
                            (
                                member.name,
                                StructureRepository._resolve(member.typ, resolved),
                            )
                            for member in type.members
                        ]
                    )
                )

            return TupleTransformer(
                [
                    StructureRepository._resolve(member.typ, resolved)
                    for member in type.members
                ]
            )

        # Other options are: TypeFunction, TypeStruct, TypeCodeoffset
        # None of them are possible. In particular TypeStruct is not possible because we parse structs without
        # info about other structs, so they will be just TypeIdentifier (unknown type).

        # TODO
        raise ValueError("XD")
