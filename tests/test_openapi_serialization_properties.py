from __future__ import annotations

from urllib.parse import unquote

import pytest
from hypothesis import given, strategies as st

from schemarouter.adapters.openapi import (
    _path_atom,
    _serialize_form_query,
    _serialize_simple_header,
    _serialize_simple_path,
)
from schemarouter.errors import NonRetryableInvocationError
from schemarouter.models import ParameterSpec

_TEXT = st.text(st.characters(blacklist_categories=("Cs",)), max_size=48)
_HEADER_TEXT = st.text(
    st.characters(blacklist_categories=("Cs",), blacklist_characters=",=\r\n"),
    max_size=48,
)
_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    _TEXT,
)


@given(_SCALARS)
def test_path_atom_round_trips_scalar_without_raw_path_delimiters(value: object) -> None:
    encoded = _path_atom(value, context="property test")

    assert unquote(encoded) == (
        "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    )
    assert "/" not in encoded
    assert "?" not in encoded
    assert "#" not in encoded
    assert " " not in encoded
    assert "." not in encoded


@given(st.lists(_SCALARS, max_size=12))
def test_simple_path_array_has_unambiguous_commas(values: list[object]) -> None:
    parameter = ParameterSpec(
        name="ids",
        location="path",
        style="simple",
        explode=False,
    )

    encoded = _serialize_simple_path(parameter, values)

    assert encoded.count(",") == max(len(values) - 1, 0)
    assert "/" not in encoded
    assert "?" not in encoded
    assert "#" not in encoded


@given(st.dictionaries(_TEXT.filter(bool), _SCALARS, max_size=10))
def test_simple_path_exploded_object_has_one_equals_per_pair(values: dict[str, object]) -> None:
    parameter = ParameterSpec(
        name="attrs",
        location="path",
        style="simple",
        explode=True,
    )

    encoded = _serialize_simple_path(parameter, values)
    parts = encoded.split(",") if encoded else []

    assert len(parts) == len(values)
    assert all(part.count("=") == 1 for part in parts)


@given(st.lists(_SCALARS, max_size=12), st.booleans())
def test_form_query_array_preserves_explode_shape(
    values: list[object],
    explode: bool,
) -> None:
    parameter = ParameterSpec(
        name="tag",
        location="query",
        style="form",
        explode=explode,
    )

    pairs = _serialize_form_query(parameter, "tag", values)

    if explode:
        assert len(pairs) == len(values)
        assert all(key == "tag" for key, _ in pairs)
    else:
        assert len(pairs) == 1
        assert pairs[0][0] == "tag"


@given(st.dictionaries(_HEADER_TEXT.filter(bool), _HEADER_TEXT, max_size=10))
def test_simple_header_exploded_object_has_one_equals_per_pair(
    values: dict[str, object],
) -> None:
    parameter = ParameterSpec(
        name="X-Meta",
        location="header",
        style="simple",
        explode=True,
    )

    serialized = _serialize_simple_header(parameter, values)
    parts = serialized.split(",") if serialized else []

    assert len(parts) == len(values)
    assert all(part.count("=") == 1 for part in parts)


def test_simple_header_preserves_application_supplied_escaping() -> None:
    parameter = ParameterSpec(
        name="X-Value",
        location="header",
        style="simple",
        explode=False,
    )

    assert _serialize_simple_header(parameter, 'W/"a,b=c"') == 'W/"a,b=c"'


@pytest.mark.parametrize(
    ("serializer", "parameter", "value"),
    [
        (
            _serialize_simple_path,
            ParameterSpec(name="p", location="path", style="simple", explode=False),
            [["nested"]],
        ),
        (
            _serialize_simple_header,
            ParameterSpec(name="h", location="header", style="simple", explode=False),
            {"nested": ["value"]},
        ),
    ],
)
def test_nested_parameter_values_fail_closed(serializer, parameter, value) -> None:
    with pytest.raises(NonRetryableInvocationError, match="nested non-scalar"):
        serializer(parameter, value)


def test_nested_form_query_values_fail_closed() -> None:
    parameter = ParameterSpec(
        name="q",
        location="query",
        style="form",
        explode=True,
    )

    with pytest.raises(NonRetryableInvocationError, match="nested non-scalar"):
        _serialize_form_query(parameter, "q", [["nested"]])
