"""Select explicit frozen #431 shards for infrastructure-only recovery."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CATALOGS = (100, 250, 500)
SHARD_RE = re.compile(r"^c(100|250|500)-g([0-5][0-9])$")


def frozen_matrix(corpus: dict[str, object]) -> dict[str, dict[str, object]]:
    tasks = corpus["tasks"]
    assert isinstance(tasks, list)
    ids = [str(task["semantic_task_id"]) for task in tasks]
    chunks = [ids[index : index + 3] for index in range(0, len(ids), 3)]
    assert len(chunks) == 60
    return {
        f"c{catalog}-g{index:02d}": {
            "job_id": f"c{catalog}-g{index:02d}",
            "catalog_size": catalog,
            "task_ids": ",".join(chunk),
        }
        for catalog in CATALOGS
        for index, chunk in enumerate(chunks)
    }


def select(corpus: dict[str, object], shard_ids: str) -> list[dict[str, object]]:
    requested = [item.strip() for item in shard_ids.split(",") if item.strip()]
    if not requested:
        raise ValueError("at least one shard ID is required")
    if len(requested) != len(set(requested)):
        raise ValueError("duplicate shard IDs are not allowed")
    matrix = frozen_matrix(corpus)
    unknown = [item for item in requested if SHARD_RE.fullmatch(item) is None or item not in matrix]
    if unknown:
        raise ValueError(f"unknown frozen shard IDs: {unknown}")
    return [matrix[item] for item in requested]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--shard-ids", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    include = select(corpus, args.shard_ids)
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write("matrix=" + json.dumps({"include": include}, separators=(",", ":")) + "\n")
    print(json.dumps({"selected": [item["job_id"] for item in include]}, sort_keys=True))


if __name__ == "__main__":
    main()
