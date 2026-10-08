"""No-model regression tests for required pinned SafeAct V1 broker runner."""

import socket
import stat
from pathlib import Path

import pytest

from scripts import check_safeact_v1_runner as runner


def test_missing_model_runtime_and_auth_fails_closed() -> None:
    report = runner.inspect_runner(backend="codex", environ={})
    assert not report["ready"]
    assert report["model_calls"] == 0
    assert report["broker_secret_values_exposed"] is False
    assert "protected runner authorization not present" in report["blockers"]
    assert "trusted model broker environment is incomplete" in report["blockers"]


def test_malformed_broker_never_reflects_sensitive_path(
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "private-credential-dir"
    secret_path.mkdir()
    env = {
        "SAFEACT_V1_RUNTIME_VERIFIED": "1",
        "SAFEACT_MODEL_BROKER_DIR": str(secret_path),
        "SAFEACT_MODEL_BROKER_SOCKET": "missing.sock",
        "SAFEACT_MODEL_BROKER_PORT": "443",
    }
    report = runner.inspect_runner(backend="codex", environ=env)
    assert not report["ready"]
    assert any("model broker" in blocker for blocker in report["blockers"])
    assert str(secret_path) not in str(report)


def test_invalid_broker_port_is_rejected(tmp_path: Path) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        socket_path = tmp_path / "broker.sock"
        sock.bind(str(socket_path))
        env = {
            "SAFEACT_V1_RUNTIME_VERIFIED": "1",
            "SAFEACT_MODEL_BROKER_DIR": str(tmp_path),
            "SAFEACT_MODEL_BROKER_SOCKET": socket_path.name,
            "SAFEACT_MODEL_BROKER_PORT": "0",
        }
        result = runner.inspect_runner(backend="claude", environ=env)
        assert not result["ready"]
        assert "trusted model broker socket/port is invalid" in result["blockers"]


@pytest.mark.parametrize("backend", ["other", "", "CODEx"])
def test_unknown_backend_cannot_launch(backend: str) -> None:
    report = runner.inspect_runner(backend=backend, environ={})
    assert not report["ready"]
    assert "backend must be codex or claude" in report["blockers"]
