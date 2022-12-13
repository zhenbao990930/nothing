from starknet_py.utils.wrapped_named_tuple import WrappedNamedTuple


# pylint: disable=protected-access
def test_wrapped_named_tuple():
    input_dict = {
        "first": 1,
        "_second": 2,
        "__third": 3,
    }
    result = WrappedNamedTuple.from_dict(input_dict)
    assert result == (1, 2, 3)
    assert (result[0], result[1], result[2]) == (1, 2, 3)
    # noinspection PyUnresolvedReferences
    assert (result.first, result._second, result.__third) == (1, 2, 3)
    assert result._asdict() == input_dict
    assert str(result) == "WrappedNamedTuple(first=1, _second=2, __third=3)"
    assert repr(result) == "WrappedNamedTuple(first=1, _second=2, __third=3)"
