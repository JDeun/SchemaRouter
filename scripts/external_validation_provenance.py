"""Shared provenance helpers for external-validation benchmark runners."""
from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def distribution_version(distribution: str | None) -> str | None:
    """Return an installed distribution version without making it mandatory."""
    if not distribution:
        return None
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def git_revision(source_path: Path | None) -> str | None:
    """Resolve the git HEAD containing source_path when it is in a checkout."""
    if source_path is None:
        return None
    directory = source_path if source_path.is_dir() else source_path.parent
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    revision = completed.stdout.strip()
    return revision or None


def implementation_provenance(
    *,
    fixture_reference_revision: str | None,
    explicit_revision: str | None = None,
    source_path: Path | None = None,
    distribution: str | None = None,
) -> dict[str, Any]:
    """Build provenance without pretending the fixture revision is the executed revision."""
    detected = explicit_revision or git_revision(source_path)
    revision_source = (
        "explicit"
        if explicit_revision
        else ("git" if detected else "unavailable")
    )
    return {
        "commit": detected,
        "commit_source": revision_source,
        "fixture_reference_revision": fixture_reference_revision,
        "package_version": distribution_version(distribution),
    }
