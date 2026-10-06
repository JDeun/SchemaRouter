from __future__ import annotations

import pytest

from schemarouter.document_loading import (
    DocumentLimitError,
    DocumentLimits,
    load_bounded_json,
    load_bounded_yaml,
    read_bounded_text,
    validate_bounded_structure,
)


def test_bounded_json_rejects_oversized_input_before_parsing(monkeypatch) -> None:
    def fail_if_called(document):
        del document
        raise AssertionError("JSON parser must not run for an oversized document")

    monkeypatch.setattr("schemarouter.document_loading.json.loads", fail_if_called)
    with pytest.raises(DocumentLimitError, match="encoded-size"):
        load_bounded_json(
            '{"value":"' + ("x" * 64) + '"}',
            limits=DocumentLimits(max_bytes=16),
        )


def test_bounded_json_rejects_depth_before_recursive_parser(monkeypatch) -> None:
    def fail_if_called(document):
        del document
        raise AssertionError("JSON parser must not run for an over-deep document")

    monkeypatch.setattr("schemarouter.document_loading.json.loads", fail_if_called)
    with pytest.raises(DocumentLimitError, match="depth"):
        load_bounded_json(
            '[[[1]]]',
            limits=DocumentLimits(max_depth=2),
        )


def test_bounded_yaml_rejects_depth_before_safe_construction(monkeypatch) -> None:
    yaml = pytest.importorskip("yaml")

    def fail_if_called(document):
        del document
        raise AssertionError("YAML constructor must not run for an over-deep document")

    monkeypatch.setattr(yaml, "safe_load", fail_if_called)
    with pytest.raises(DocumentLimitError, match="depth"):
        load_bounded_yaml(
            "a:\n  b:\n    c: 1\n",
            limits=DocumentLimits(max_depth=2),
        )


def test_bounded_structure_rejects_depth_nodes_and_container_cardinality() -> None:
    with pytest.raises(DocumentLimitError, match="depth"):
        validate_bounded_structure(
            {"a": {"b": {"c": 1}}},
            limits=DocumentLimits(max_depth=2),
        )

    with pytest.raises(DocumentLimitError, match="node"):
        validate_bounded_structure(
            [1, 2, 3],
            limits=DocumentLimits(max_nodes=3),
        )

    with pytest.raises(DocumentLimitError, match="collection item"):
        validate_bounded_structure(
            [1, 2, 3],
            limits=DocumentLimits(max_container_items=2),
        )


def test_bounded_yaml_rejects_alias_fanout_and_cycles() -> None:
    pytest.importorskip("yaml")

    with pytest.raises(DocumentLimitError, match="alias"):
        load_bounded_yaml(
            "base: &base {value: 1}\na: *base\nb: *base\n",
            limits=DocumentLimits(max_yaml_aliases=1),
        )

    with pytest.raises(DocumentLimitError, match="cyclic"):
        load_bounded_yaml("root: &root [*root]\n")


def test_read_bounded_text_stops_after_limit(tmp_path) -> None:
    source = tmp_path / "large.json"
    source.write_bytes(b"x" * 32)

    with pytest.raises(DocumentLimitError, match="encoded-size"):
        read_bounded_text(source, limits=DocumentLimits(max_bytes=16))
