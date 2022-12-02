from __future__ import annotations
from collections import OrderedDict, defaultdict
from typing import List, Dict, DefaultDict, Sequence, Optional

from starkware.cairo.lang.compiler.parser import parse_type
import starkware.cairo.lang.compiler.ast.cairo_types as cairo_lang_types

from starknet_py.cairo.data_types import (
    UnknownType,
    CairoType,
    FeltType,
    TupleType,
    NamedTupleTuple,
    ArrayType,
    StructType,
    InlineType,
)


class TypeParser:
    defined_structs: Optional[Dict[str, StructType]]

    def __init__(self, defined_structs: Optional[Dict[str, StructType]] = None):
        """
        TypeParser constructor.
        :param defined_structs: dictionary containing _all_ defined structures. When provided parser will ensure that
        resulting type is already resolved and will throw if some type is missing
        """
        self.defined_structs = defined_structs

    def parse_inline_type(self, type_string: str) -> InlineType:
        """
        Inline type it one that can be used inline. For instance (a: felt, b: felt*, c: (felt, felt)).
        Structs can't be defined inline, so it will never be returned.
        :param type_string: type to parse
        """
        parsed = parse_type(type_string)
        return self._transform_cairo_lang_type(parsed)

    def _transform_cairo_lang_type(
        self, cairo_type: cairo_lang_types.CairoType
    ) -> CairoType:
        if isinstance(cairo_type, cairo_lang_types.TypeFelt):
            return FeltType()

        if isinstance(cairo_type, cairo_lang_types.TypePointer):
            return ArrayType(self._transform_cairo_lang_type(cairo_type.pointee))

        if isinstance(cairo_type, cairo_lang_types.TypeIdentifier):
            name = str(cairo_type.name)
            if self.defined_structs is not None:
                # When we use defined structs we want to make sure there will be no UnknownType.
                if name not in self.defined_structs:
                    raise ValueError(f"Structure [{name}] is not defined")

                return self.defined_structs[name]

            return UnknownType(str(cairo_type.name))

        if isinstance(cairo_type, cairo_lang_types.TypeTuple):
            if cairo_type.is_named:
                return NamedTupleTuple(
                    OrderedDict(
                        (member.name, self._transform_cairo_lang_type(member.typ))
                        for member in cairo_type.members
                    )
                )

            return TupleType(
                [
                    self._transform_cairo_lang_type(member.typ)
                    for member in cairo_type.members
                ]
            )

        # Other options are: TypeFunction, TypeStruct, TypeCodeoffset
        # None of them are possible. In particular TypeStruct is not possible because we parse structs without
        # info about other structs, so they will be just TypeIdentifier (unknown type).
        raise ValueError(f"Unknown type [{cairo_type.__name__}: {cairo_type}]")
