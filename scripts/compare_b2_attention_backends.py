"""Compare eager and SDPA B2 outputs after removing timing/backend metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TIMING_KEYS = {
    "model_load_ms",
}


def _is_timing_key(key: str) -> bool:
    return key in TIMING_KEYS or "latency_ms" in key


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if _is_timing_key(key):
                continue
            if key == "runtime":
                continue
            if key == "attention_implementation":
                continue
            normalized[key] = _normalize(child)
        return normalized
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eager", type=Path, required=True)
    parser.add_argument("--sdpa", type=Path, required=True)
    args = parser.parse_args()

    eager = json.loads(args.eager.read_text(encoding="utf-8"))
    sdpa = json.loads(args.sdpa.read_text(encoding="utf-8"))

    eager_norm = _normalize(eager)
    sdpa_norm = _normalize(sdpa)
    if eager_norm != sdpa_norm:
        eager_rows = {
            (
                int(row["catalog_size"]),
                str(row["task_id"]),
                str(row["condition"]),
            ): _normalize(row)
            for row in eager["rows"]
        }
        sdpa_rows = {
            (
                int(row["catalog_size"]),
                str(row["task_id"]),
                str(row["condition"]),
            ): _normalize(row)
            for row in sdpa["rows"]
        }
        differing = [
            key
            for key in sorted(set(eager_rows) | set(sdpa_rows))
            if eager_rows.get(key) != sdpa_rows.get(key)
        ]
        raise SystemExit(
            "B2 eager/SDPA behavioral mismatch: "
            + ", ".join(str(key) for key in differing[:20])
        )

    print(
        json.dumps(
            {
                "equivalent": True,
                "row_count": len(eager["rows"]),
                "catalog_sizes": eager["catalog_sizes"],
                "task_ids": eager["task_ids"],
                "conditions": eager["conditions"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
