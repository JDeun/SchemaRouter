"""Generate the frozen adaptive-context confirmation corpus without scoring it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.agent_utility_prior_query_guard import (
    assert_no_prior_query_overlap,
    normalize_query,
)
from scripts.external_validation_gearlynx import CASES as GEARLYNX_CASES

LANGUAGES = ("en", "ko")
KINDS = ("single", "multi", "near_unsupported", "ood_unsupported")
PER_LANGUAGE_KIND = 15


def _query(language: str, kind: str, index: int) -> str:
    token = f"ACF-{language.upper()}-{kind.upper()}-{index:02d}"
    if language == "en":
        templates = {
            "single": (
                f"{token}. Read the current Young's modulus for material "
                f"CONF-{index:03d} in GPa."
            ),
            "multi": (
                f"{token}. Search papers about confirmation alloy {index}, then "
                "retrieve the selected paper using its returned identifier."
            ),
            "near_unsupported": (
                f"{token}. Use the registered neutron diffraction refinement "
                f"capability for specimen CONF-{index:03d}."
            ),
            "ood_unsupported": (
                f"{token}. Book a restaurant table for confirmation guest "
                f"{index} tonight."
            ),
        }
    else:
        templates = {
            "single": (
                f"{token}. 재료 CONF-{index:03d}의 현재 영률을 GPa 단위로 "
                "조회하세요."
            ),
            "multi": (
                f"{token}. 확인용 합금 {index} 관련 논문을 검색하고 반환된 식별자로 "
                "선택 논문을 조회하세요."
            ),
            "near_unsupported": (
                f"{token}. 시료 CONF-{index:03d}에 등록된 중성자 회절 정련 기능을 "
                "사용하세요."
            ),
            "ood_unsupported": (
                f"{token}. 오늘 밤 확인용 손님 {index} 이름으로 식당 좌석을 예약하세요."
            ),
        }
    return templates[kind]


def build_corpus() -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    task_id = 1
    for language in LANGUAGES:
        for kind in KINDS:
            for index in range(1, PER_LANGUAGE_KIND + 1):
                supported = kind in {"single", "multi"}
                required_routes = (
                    ["materials.current"]
                    if kind == "single"
                    else ["papers.search", "papers.retrieve"]
                    if kind == "multi"
                    else []
                )
                tasks.append(
                    {
                        "task_id": f"acf-{task_id:03d}",
                        "language": language,
                        "kind": kind,
                        "supported": supported,
                        "query": _query(language, kind, index),
                        "required_routes": required_routes,
                    }
                )
                task_id += 1

    normalized = {normalize_query(str(task["query"])) for task in tasks}
    if len(normalized) != len(tasks):
        raise RuntimeError("confirmation corpus produced duplicate normalized queries")
    gearlynx = {
        normalize_query(query)
        for query, required in GEARLYNX_CASES
        if required is None
    }
    assert_no_prior_query_overlap(normalized, extra_forbidden_queries=gearlynx)
    canonical = json.dumps(
        tasks, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "issue": 840,
        "benchmark": "adaptive-context-confirmation-v1",
        "status": "frozen_unscored",
        "task_count": len(tasks),
        "languages": list(LANGUAGES),
        "kinds": list(KINDS),
        "tasks_sha256": hashlib.sha256(canonical).hexdigest(),
        "tasks": tasks,
    }


def main() -> None:
    out = Path("benchmarks/adaptive-context-confirmation-v1/corpus.json")
    corpus = build_corpus()
    out.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(corpus["tasks_sha256"])


if __name__ == "__main__":
    main()
