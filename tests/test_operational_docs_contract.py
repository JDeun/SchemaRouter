from __future__ import annotations

from pathlib import Path

import schemarouter


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_lifecycle_docs_track_owned_background_apis() -> None:
    assert hasattr(schemarouter.SchemaRouter, "start_native_schema_watcher")
    assert hasattr(schemarouter.SchemaRouter, "stop_native_schema_watcher")
    assert hasattr(schemarouter.SchemaRouter, "aclose")

    for path in ("docs/guides/runtime.md", "docs_ko/guides/runtime.md"):
        text = _read(path)
        assert "start_native_schema_watcher" in text
        assert "stop_native_schema_watcher" in text
        assert "aclose()" in text
        assert "AccessHealthMonitor" in text
        assert "SchemaWatchManager" in text


def test_retry_docs_name_the_explicit_invocation_failure_taxonomy() -> None:
    assert issubclass(
        schemarouter.InvocationUnavailableError,
        schemarouter.TransientInvocationError,
    )
    assert issubclass(
        schemarouter.IndeterminateInvocationError,
        schemarouter.NonRetryableInvocationError,
    )

    expected = (
        "TransientInvocationError",
        "InvocationUnavailableError",
        "NonRetryableInvocationError",
        "IndeterminateInvocationError",
    )
    for path in ("docs/guides/retry.md", "docs_ko/guides/retry.md"):
        text = _read(path)
        for symbol in expected:
            assert symbol in text


def test_authorization_docs_keep_lint_enabled_by_default() -> None:
    assert callable(schemarouter.parse_authorization_policy)

    for path in (
        "docs/guides/authorization.md",
        "docs_ko/guides/authorization.md",
    ):
        text = _read(path)
        assert "parse_authorization_policy" in text
        assert "lint=True" in text
        assert "first-match" in text.lower()
