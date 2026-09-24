from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_artifact_digest.py"


def _run(
    built: Path,
    published: Path,
    kind: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--built-dir",
            str(built),
            "--published-dir",
            str(published),
            "--artifact-kind",
            kind,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("kind", "filename"),
    [
        ("wheel", "schemarouter-0.7.0-py3-none-any.whl"),
        ("sdist", "schemarouter-0.7.0.tar.gz"),
    ],
)
def test_artifact_digest_accepts_identical_release_bytes(
    tmp_path: Path,
    kind: str,
    filename: str,
) -> None:
    built = tmp_path / "built"
    published = tmp_path / "published"
    built.mkdir()
    published.mkdir()
    payload = b"trusted-release-artifact"
    (built / filename).write_bytes(payload)
    (published / filename).write_bytes(payload)

    result = _run(built, published, kind)

    assert result.returncode == 0, result.stderr
    assert "Verified PyPI artifact SHA-256" in result.stdout


def test_artifact_digest_rejects_modified_published_bytes(tmp_path: Path) -> None:
    built = tmp_path / "built"
    published = tmp_path / "published"
    built.mkdir()
    published.mkdir()
    filename = "schemarouter-0.7.0-py3-none-any.whl"
    (built / filename).write_bytes(b"trusted")
    (published / filename).write_bytes(b"modified")

    result = _run(built, published, "wheel")

    assert result.returncode != 0
    assert "artifact SHA-256 mismatch" in result.stderr


def test_artifact_digest_rejects_filename_mismatch(tmp_path: Path) -> None:
    built = tmp_path / "built"
    published = tmp_path / "published"
    built.mkdir()
    published.mkdir()
    (built / "schemarouter-0.7.0-py3-none-any.whl").write_bytes(b"same")
    (published / "schemarouter-0.7.1-py3-none-any.whl").write_bytes(b"same")

    result = _run(built, published, "wheel")

    assert result.returncode != 0
    assert "artifact filename mismatch" in result.stderr


def test_artifact_digest_rejects_ambiguous_artifact_set(tmp_path: Path) -> None:
    built = tmp_path / "built"
    published = tmp_path / "published"
    built.mkdir()
    published.mkdir()
    (built / "schemarouter-0.7.0-py3-none-any.whl").write_bytes(b"a")
    (built / "schemarouter-0.7.1-py3-none-any.whl").write_bytes(b"b")
    (published / "schemarouter-0.7.0-py3-none-any.whl").write_bytes(b"a")

    result = _run(built, published, "wheel")

    assert result.returncode != 0
    assert "expected exactly one wheel artifact" in result.stderr
