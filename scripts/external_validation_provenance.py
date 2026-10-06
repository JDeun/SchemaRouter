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
    """Resolve HEAD only when source_path is actually tracked by that checkout."""
    if source_path is None:
        return None

    source = source_path.resolve()
    directory = source if source.is_dir() else source.parent
    try:
        root_result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        root = Path(root_result.stdout.strip()).resolve()
        relative = source.relative_to(root)
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", str(relative)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if tracked.returncode != 0:
            return None
        revision_result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    revision = revision_result.stdout.strip()
    return revision or None


def implementation_provenance(
    *,
    fixture_reference_revision: str | None,
    explicit_revision: str | None = None,
    source_path: Path | None = None,
    distribution: str | None = None,
) -> dict[str, Any]:
    """Build provenance without pretending the fixture revision is the executed revision."""
    detected_git = git_revision(source_path)
    if (
        explicit_revision is not None
        and detected_git is not None
        and explicit_revision != detected_git
    ):
        raise ValueError(
            "explicit implementation revision does not match the executed git checkout"
        )
    detected = explicit_revision or detected_git
    revision_source = (
        "explicit"
        if explicit_revision
        else ("git" if detected_git else "unavailable")
    )
    return {
        "commit": detected,
        "commit_source": revision_source,
        "fixture_reference_revision": fixture_reference_revision,
        "package_version": distribution_version(distribution),
    }
