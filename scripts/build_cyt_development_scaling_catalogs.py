"""Build deterministic development-only CYT scaling catalogs.

Synthetic distractors are development-only. They are never promoted into held-out evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SIZES = (100, 250, 500, 1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    base = list(source["tools"])
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        tools = list(base)
        for i in range(1, size - len(base) + 1):
            tools.append(
                {
                    "name": f"synthetic_dev_distractor_{i:04d}",
                    "description": (
                        f"Development distractor capability {i:04d}; synthetic and "
                        "not relevant to benchmark tasks."
                    ),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": "string",
                                "description": f"Synthetic development value {i:04d}",
                            }
                        },
                    },
                }
            )
        payload = {
            "schema_version": 1,
            "status": "development_unfrozen",
            "synthetic_distractors": True,
            "tools": tools[:size],
        }
        raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
        path = args.out_dir / f"catalog-{size}.json"
        path.write_bytes(raw)
        print(size, hashlib.sha256(raw).hexdigest(), path)


if __name__ == "__main__":
    main()
