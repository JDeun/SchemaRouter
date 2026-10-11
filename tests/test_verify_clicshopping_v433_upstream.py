"""Regression tests for pinned upstream file verification."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_clicshopping_v433_upstream import git_blob_sha, php_action_arrays


def test_git_blob_identity_is_git_compatible():
    # Git SHA-1 includes a blob header, not a raw byte hash.
    assert git_blob_sha(b"test content\n") == "d670460b4b4aece5915caf5c68d12f560a9fe3e4"


def test_exact_php_permission_declarations_not_scored_output():
    source = """
    private const READ_ACTIONS = ['products', 'search',];
    private const WRITE_ACTIONS = [
        'cancel' => ['update_data'],
        'create' => ['create_data', 'update_data'],
    ];
    """
    result = php_action_arrays(source)
    assert result["READ_ACTIONS"] == ("products", "search")
    assert result["WRITE_ACTIONS"] == ("cancel", "create")


def test_duplicate_upstream_policy_action_fails_closed():
    source = "private const READ_ACTIONS = ['products', 'products'];"
    with pytest.raises(ValueError, match="duplicate action"):
        php_action_arrays(source)


def test_duplicate_policy_constant_fails_closed():
    source = "private const READ_ACTIONS = ['one']; private const READ_ACTIONS = ['two'];"
    with pytest.raises(ValueError, match="duplicate action policy"):
        php_action_arrays(source)


def test_no_php_execution_network_calls_or_model_scoring():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/verify_clicshopping_v433_upstream.py").read_text()
    assert "subprocess.check_output" in source
    assert "read_bytes()" in source
    assert "model_calls" in source
    assert '"scored": False' in source
    assert "urlopen" not in source
    assert "php -f" not in source
