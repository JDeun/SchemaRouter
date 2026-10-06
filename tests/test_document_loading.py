import json

import pytest

from schemarouter._document_loading import (
    DocumentLimitError,
    load_bounded_json,
    load_bounded_yaml,
    read_bounded_text,
)
from schemarouter.storage import PersistedDocumentLimits


def _limits(**overrides: int) -> PersistedDocumentLimits:
    values = {
        "max_bytes": 4096,
        "max_depth": 16,
        "max_nodes": 1000,
        "max_list_items": 100,
        "max_map_items": 100,
        "max_aliases": 8,
        "max_anchors": 8,
    }
    values.update(overrides)
    return PersistedDocumentLimits(**values)


def test_bounded_json_rejects_size_depth_and_collection_cardinality() -> None:
    with pytest.raises(DocumentLimitError, match="byte limit"):
        load_bounded_json(
            json.dumps({"value": "x" * 256}),
            limits=_limits(max_bytes=64),
        )

    deep = "[" * 10 + "0" + "]" * 10
    with pytest.raises(DocumentLimitError, match="structural limits"):
        load_bounded_json(deep, limits=_limits(max_depth=4))

    with pytest.raises(DocumentLimitError, match="list cardinality"):
        load_bounded_json(
            json.dumps({"items": [1, 2, 3]}),
            limits=_limits(max_list_items=2),
        )


def test_bounded_json_round_trip_is_unchanged() -> None:
    payload = {"name": "router", "values": [1, 2, 3]}
    assert load_bounded_json(json.dumps(payload), limits=_limits()) == payload


def test_bounded_yaml_rejects_alias_budget_and_cycles() -> None:
    pytest.importorskip("yaml")

    alias_heavy = """
base: &base
  value: 1
one: *base
two: *base
"""
    with pytest.raises(DocumentLimitError, match="alias limit"):
        load_bounded_yaml(
            alias_heavy,
            limits=_limits(max_aliases=1),
        )

    cyclic = "root: &root [*root]\n"
    with pytest.raises(DocumentLimitError, match="cyclic sequence"):
        load_bounded_yaml(cyclic, limits=_limits())


def test_bounded_yaml_round_trip_is_unchanged() -> None:
    pytest.importorskip("yaml")

    payload = load_bounded_yaml(
        "version: 1\nrules:\n  - effect: allow\n",
        limits=_limits(),
    )
    assert payload == {"version": 1, "rules": [{"effect": "allow"}]}


def test_bounded_file_read_rechecks_size_after_stat(tmp_path) -> None:
    source = tmp_path / "document.json"
    source.write_bytes(b"x" * 65)

    with pytest.raises(DocumentLimitError, match="byte limit"):
        read_bounded_text(
            source,
            limits=_limits(max_bytes=64),
        )
