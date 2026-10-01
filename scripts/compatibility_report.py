"""Shared machine-readable reporting helpers for live compatibility smokes."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def new_report(
    *,
    adapter: str,
    source: str,
    provider: str | None = None,
    evidence_mode: str = "live-provider",
    authentication: str = "unknown",
) -> dict[str, Any]:
    try:
        package_version = version("schemarouter")
    except PackageNotFoundError:
        package_version = "0+unknown"

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schemarouter_version": package_version,
        "adapter": adapter,
        "provider": provider,
        "source": source,
        "evidence_mode": evidence_mode,
        "authentication": authentication,
        "status": "pending",
        "discovery": {
            "success": False,
            "tool_count": None,
            "endpoint_count": None,
            "execution_bound": None,
            "latency_ms": None,
        },
        "execution": {
            "attempted": False,
            "safe_read_only": None,
            "endpoint": None,
            "success": False,
            "latency_ms": None,
            "result_shape": None,
        },
        "known_quirks": [],
        "environment": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }


def write_report(path: str | Path | None, report: dict[str, Any]) -> None:
    if path is None:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
