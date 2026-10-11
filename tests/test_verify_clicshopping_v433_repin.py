"""Offline integrity tests for the new 4.33 maintainer-specified source pin."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_clicshopping_v433_repin import (
    APP,
    HISTORICAL,
    NEW_PAGE,
    NEW_PAGE_SHA,
    REPinned,
    dispatch_actions,
    git_blob_sha,
    source_bytes,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks/external-validation-clicshopping-v433"


def test_repin_metadata_preserves_historical_dev_freeze() -> None:
    manifest = json.loads(
        (PACKAGE / "maintainer-repin-8ada7f1.json").read_text()
    )
    historical = json.loads((PACKAGE / "source-inventory.json").read_text())
    assert manifest["historical_dev_pin"] == HISTORICAL
    assert historical["upstream"]["commit"] == HISTORICAL
    assert manifest["new_source_pin"] == REPinned
    assert manifest["new_customer_orders_page"]["git_blob_sha"] == NEW_PAGE_SHA
    assert historical["endpoints"]["customerOrders"]["page_source"]["present"] is False
    assert not manifest["source_verification"]["heldout_approved"]


def test_detects_all_expected_literal_dispatch_actions() -> None:
    source = """
    match ($action) {
        'list_orders' => $this->handleListOrders(),
        'read_order' => $this->handleReadOrder(),
        'cancel_order' => $this->handleCancelOrder(),
        'send_message' => $this->handleSendMessage(),
        'history' => $this->handleGetHistory(),
    };
    """
    assert dispatch_actions(source) == {
        "list_orders", "read_order", "cancel_order", "send_message", "history"
    }


def test_rejects_duplicate_action_dispatch() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        dispatch_actions(
            "'history' => $this->handleGetHistory(), "
            "'history' => $this->handleGetHistory(),"
        )


def test_rejects_tampered_bytes_and_path_traversal(tmp_path: Path) -> None:
    path = tmp_path / NEW_PAGE
    path.parent.mkdir(parents=True)
    path.write_bytes(b"<?php\n")
    digest = git_blob_sha(b"<?php\n")
    assert source_bytes(tmp_path, NEW_PAGE, digest) == b"<?php\n"
    with pytest.raises(ValueError, match="blob mismatch"):
        source_bytes(tmp_path, NEW_PAGE, "0" * 40)
    with pytest.raises(ValueError, match="untrusted public-source path"):
        source_bytes(tmp_path, "../secrets.php", digest)


def test_source_transition_rejects_unapproved_scoring(tmp_path: Path) -> None:
    manifest = json.loads(
        (PACKAGE / "maintainer-repin-8ada7f1.json").read_text()
    )
    historic = json.loads((PACKAGE / "source-inventory.json").read_text())
    manifest["source_verification"]["heldout_approved"] = True
    with pytest.raises(ValueError, match="source-only evaluation boundary"):
        verify(tmp_path, manifest, historic)


def test_source_transition_rejects_revision_swap(tmp_path: Path) -> None:
    manifest = json.loads(
        (PACKAGE / "maintainer-repin-8ada7f1.json").read_text()
    )
    historic = json.loads((PACKAGE / "source-inventory.json").read_text())
    manifest["new_source_pin"] = "0" * 40
    with pytest.raises(ValueError, match="maintainer source transition"):
        verify(tmp_path, manifest, historic)


def test_source_transition_rejects_fake_permission_sha(tmp_path: Path) -> None:
    manifest = json.loads(
        (PACKAGE / "maintainer-repin-8ada7f1.json").read_text()
    )
    historic = json.loads((PACKAGE / "source-inventory.json").read_text())
    historic["endpoints"]["customerOrders"]["permission_source"][
        "git_blob_sha"
    ] = "0" * 40
    with pytest.raises(ValueError, match="historical source matrix"):
        verify(tmp_path, manifest, historic)


def test_action_dispatch_never_infers_metadata_without_source() -> None:
    assert dispatch_actions(
        "private const READ_ACTIONS = ['history']; "
        "// 'history' is not proven routed."
    ) == set()
