from __future__ import annotations

import json

import pytest

from schemarouter import ConfigurationDocumentError, ConfigurationDocumentLimits
from schemarouter.authorization_config import (
    normalized_authorization_json,
    parse_authorization_policy,
)
from schemarouter.capability_artifact import (
    build_capability_artifact,
    load_capability_artifact,
    serialize_capability_artifact,
)
from schemarouter.capability_snapshot import (
    build_capability_snapshot,
    build_capability_snapshot_document,
    load_capability_snapshot,
    serialize_capability_snapshot,
)
from schemarouter.cli import _run, build_parser
from schemarouter.document_loading import (
    load_bounded_json,
    load_bounded_yaml,
    read_bounded_text_file,
)


def _policy() -> dict[str, object]:
    return {
        "version": 1,
        "default_effect": "deny",
        "rules": [],
        "data_rules": [],
    }


def test_bounded_json_rejects_encoded_size_before_decode() -> None:
    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        load_bounded_json(
            '{"value":"abcdefgh"}',
            limits=ConfigurationDocumentLimits(max_bytes=8),
        )


def test_bounded_json_rejects_deep_document_before_decode() -> None:
    with pytest.raises(ConfigurationDocumentError, match="depth limit"):
        load_bounded_json(
            '[[[1]]]',
            limits=ConfigurationDocumentLimits(max_depth=2),
        )


def test_bounded_json_rejects_large_decoded_container() -> None:
    with pytest.raises(ConfigurationDocumentError, match="item limit"):
        load_bounded_json(
            '[1,2,3]',
            limits=ConfigurationDocumentLimits(max_container_items=2),
        )


def test_bounded_yaml_rejects_alias_expansion_budget() -> None:
    pytest.importorskip("yaml")
    document = """
base: &base
  - 1
first: *base
second: *base
"""
    with pytest.raises(ConfigurationDocumentError, match="alias limit"):
        load_bounded_yaml(
            document,
            limits=ConfigurationDocumentLimits(max_yaml_aliases=1),
        )


def test_bounded_yaml_rejects_cyclic_alias_structure() -> None:
    pytest.importorskip("yaml")
    document = """
loop: &loop
  - *loop
"""
    with pytest.raises(ConfigurationDocumentError, match="cyclic"):
        load_bounded_yaml(document)


def test_bounded_file_read_rejects_oversized_file(tmp_path) -> None:
    source = tmp_path / "config.json"
    source.write_text('{"value":"abcdefgh"}', encoding="utf-8")

    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        read_bounded_text_file(
            source,
            limits=ConfigurationDocumentLimits(max_bytes=8),
        )


def test_capability_artifact_loader_accepts_custom_document_budget() -> None:
    artifact = build_capability_artifact(
        graph_digest="g",
        capabilities=[],
    )
    document = serialize_capability_artifact(artifact)

    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        load_capability_artifact(
            document,
            document_limits=ConfigurationDocumentLimits(
                max_bytes=max(1, len(document.encode("utf-8")) - 1)
            ),
        )


def test_capability_snapshot_loader_accepts_custom_document_budget() -> None:
    snapshot = build_capability_snapshot([])
    document = serialize_capability_snapshot(
        build_capability_snapshot_document(snapshot)
    )

    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        load_capability_snapshot(
            document,
            document_limits=ConfigurationDocumentLimits(
                max_bytes=max(1, len(document.encode("utf-8")) - 1)
            ),
        )


def test_authorization_policy_json_uses_document_budget() -> None:
    document = json.dumps(_policy())

    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        parse_authorization_policy(
            document,
            document_limits=ConfigurationDocumentLimits(
                max_bytes=max(1, len(document.encode("utf-8")) - 1)
            ),
        )


def test_authorization_policy_yaml_uses_alias_budget() -> None:
    pytest.importorskip("yaml")
    document = """
version: 1
default_effect: deny
rules: &rules []
data_rules: *rules
extra_rules: *rules
"""
    with pytest.raises(ConfigurationDocumentError, match="alias limit"):
        parse_authorization_policy(
            document,
            format="yaml",
            document_limits=ConfigurationDocumentLimits(max_yaml_aliases=1),
        )


def test_authorization_policy_dict_uses_structural_budget() -> None:
    policy = _policy()
    policy["metadata"] = {"a": 1, "b": 2, "c": 3}

    with pytest.raises(ConfigurationDocumentError, match="item limit"):
        parse_authorization_policy(
            policy,
            document_limits=ConfigurationDocumentLimits(max_container_items=2),
        )


def test_normalized_authorization_json_uses_document_budget() -> None:
    document = json.dumps(_policy())

    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        normalized_authorization_json(
            document,
            document_limits=ConfigurationDocumentLimits(
                max_bytes=max(1, len(document.encode("utf-8")) - 1)
            ),
        )


def test_cli_artifact_inspection_uses_bounded_reader(tmp_path, monkeypatch) -> None:
    source = tmp_path / "artifact.json"
    source.write_text("{}", encoding="utf-8")
    args = build_parser().parse_args(["artifact", "inspect", str(source), "--json"])

    def reject_read(path):
        assert path == source
        raise ConfigurationDocumentError("configuration document exceeds the configured byte limit")

    monkeypatch.setattr("schemarouter.cli.read_bounded_text_file", reject_read)
    with pytest.raises(ConfigurationDocumentError, match="byte limit"):
        _run(args)
