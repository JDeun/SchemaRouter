"""Unhinted natural-language route selection on real anonymous public sources.

Research-only E1 observation: source-shaped host labels are NOT independent
semantic gold, model decisions or production authorization. No route executes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import Any

from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter
from scripts.research_public_heterogeneous_live_e1 import (
    COD_URL,
    DEEPWIKI_URL,
    bounded_public_mcp_client_factory,
)


@dataclass(frozen=True)
class SourceQueryCase:
    id: str
    language: str
    query: str
    expected_route: str | None
    expected_fields: tuple[str, ...] = ()


# These targets are withheld from PlanRequest and used only to score a
# genuinely unhinted retrieval. Each source is independently documented.
CASES = (
    SourceQueryCase(
        "crossref_doi_en",
        "en",
        "Look up the article title and publication metadata for DOI 10.1038/nature12373",
        "crossref.get_work",
        ("message",),
    ),
    SourceQueryCase(
        "cod_si_o_en",
        "en",
        "Find Si O binary crystal structures and their chemical formula",
        "cod_public.search_structures",
        ("chemical_formula_descriptive", "nelements", "elements"),
    ),
    SourceQueryCase(
        "wiki_structure_en",
        "en",
        "Read the public repository wiki structure for modelcontextprotocol/servers",
        "deepwiki_public.read_wiki_structure",
        ("result",),
    ),
    SourceQueryCase(
        "crossref_doi_ko",
        "ko",
        "DOI 10.1038/nature12373 논문의 제목과 서지 정보를 찾아줘",
        "crossref.get_work",
        ("message",),
    ),
    SourceQueryCase(
        "cod_si_o_ko",
        "ko",
        "실리콘과 산소가 포함된 결정 구조를 검색해줘",
        "cod_public.search_structures",
        ("chemical_formula_descriptive", "nelements", "elements"),
    ),
    SourceQueryCase(
        "wiki_structure_ko",
        "ko",
        "modelcontextprotocol/servers 저장소의 문서 목차를 읽어줘",
        "deepwiki_public.read_wiki_structure",
        ("result",),
    ),
    SourceQueryCase(
        "crossref_doi_ja",
        "ja",
        "DOI 10.1038/nature12373 の論文タイトルと出版メタデータを調べて",
        "crossref.get_work",
        ("message",),
    ),
    SourceQueryCase(
        "cod_si_o_ja",
        "ja",
        "SiとOの結晶構造と化学式を検索して",
        "cod_public.search_structures",
        ("chemical_formula_descriptive", "nelements", "elements"),
    ),
    SourceQueryCase(
        "wiki_structure_ja",
        "ja",
        "modelcontextprotocol/servers リポジトリのウィキ構造を読んで",
        "deepwiki_public.read_wiki_structure",
        ("result",),
    ),
    SourceQueryCase(
        "negative_credentials_en",
        "en",
        "Please rotate the deployment access tokens",
        None,
    ),
    SourceQueryCase(
        "negative_credentials_ko",
        "ko",
        "운영 서버 비밀번호를 즉시 초기화해줘",
        None,
    ),
    SourceQueryCase(
        "negative_records_ja",
        "ja",
        "顧客アカウントを削除して",
        None,
    ),
)


def live_source_contract_provenance() -> dict[str, dict[str, Any]]:
    """Identify real discovery versus a bundled original-source profile.

    The earlier execution matrix exercised Crossref's public REST API, but
    add_provider("crossref") by itself does not fetch its remote schema.
    """
    return {
        "crossref": {
            "contract_origin": "bundled_crossref_provider_profile",
            "live_remote_schema_discovered": False,
        },
        "cod_public": {
            "contract_origin": "live_optimade_service_metadata",
            "live_remote_schema_discovered": True,
        },
        "deepwiki_public": {
            "contract_origin": "live_mcp_tool_listing",
            "live_remote_schema_discovered": True,
        },
    }


def _ranked_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = row.get("candidates")
    if not isinstance(ranked, list) or len(ranked) > 5:
        raise ValueError("case candidates must contain at most native Top-5")
    seen: set[str] = set()
    for candidate in ranked:
        if not isinstance(candidate, dict):
            raise ValueError("route candidate not an object")
        route_id = candidate.get("route_id")
        score = candidate.get("score")
        if not isinstance(route_id, str) or not route_id or route_id in seen:
            raise ValueError("duplicate or missing native route")
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(score)
            or score < 0
        ):
            raise ValueError("native route score must be finite nonnegative")
        seen.add(route_id)
    return ranked


def score_selection_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Host-labeled retrieval metrics with strict zero-score abstention."""
    ids: set[str] = set()
    by_language: dict[str, dict[str, int]] = {}
    labeled_cases = positive_top1_hits = positive_top5_hits = 0
    raw_top1_hits = raw_top5_hits = 0
    offtopic_cases = offtopic_abstentions = zero_score_exposed_cases = 0
    offtopic_native_plan_proposals = 0
    native_plan_exact_route_hits = native_plan_expected_field_complete_hits = 0
    native_plan_required_argument_gaps = 0
    for row in rows:
        case_id, language, expected = (row.get(k) for k in ("id", "language", "expected_route"))
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("duplicate or missing case ID")
        if language not in ("en", "ko", "ja"):
            raise ValueError("case language not in frozen language set")
        if expected is not None and (not isinstance(expected, str) or not expected):
            raise ValueError("case expected native route invalid")
        ids.add(case_id)
        planned_route = row.get("planned_route")
        if planned_route is not None and (not isinstance(planned_route, str) or not planned_route):
            raise ValueError("invalid native planned route")
        ranked = _ranked_candidates(row)
        positive = [c for c in ranked if c["score"] > 0]
        if any(c["score"] == 0 for c in ranked):
            zero_score_exposed_cases += 1
        per_lang = by_language.setdefault(
            language,
            {
                "labeled": 0,
                "top1_hits": 0,
                "top5_hits": 0,
                "offtopic": 0,
                "abstentions": 0,
            },
        )
        if expected is None:
            offtopic_cases += 1
            per_lang["offtopic"] += 1
            if planned_route is not None:
                offtopic_native_plan_proposals += 1
            if not positive:
                offtopic_abstentions += 1
                per_lang["abstentions"] += 1
            continue
        labeled_cases += 1
        per_lang["labeled"] += 1
        if planned_route == expected:
            native_plan_exact_route_hits += 1
            expected_fields = row.get("required_expected_fields", [])
            planned_fields = row.get("planned_fields", [])
            missing_arguments = row.get("missing_required_arguments", [])
            if (
                isinstance(expected_fields, list)
                and bool(expected_fields)
                and isinstance(planned_fields, list)
                and set(expected_fields).issubset(set(planned_fields))
            ):
                native_plan_expected_field_complete_hits += 1
            if isinstance(missing_arguments, list) and missing_arguments:
                native_plan_required_argument_gaps += 1
        if ranked and ranked[0]["route_id"] == expected:
            raw_top1_hits += 1
        if any(c["route_id"] == expected for c in ranked):
            raw_top5_hits += 1
        if positive and positive[0]["route_id"] == expected:
            positive_top1_hits += 1
            per_lang["top1_hits"] += 1
        if any(c["route_id"] == expected for c in positive):
            positive_top5_hits += 1
            per_lang["top5_hits"] += 1
    if not rows or labeled_cases <= 0 or offtopic_cases <= 0:
        raise ValueError("case study requires labeled and negative query denominators")
    return {
        "total_cases": len(rows),
        "labeled_cases": labeled_cases,
        "offtopic_cases": offtopic_cases,
        "raw_top1_hits": raw_top1_hits,
        "raw_top5_hits": raw_top5_hits,
        "positive_top1_hits": positive_top1_hits,
        "positive_top5_hits": positive_top5_hits,
        "offtopic_abstentions": offtopic_abstentions,
        "offtopic_native_plan_proposals": offtopic_native_plan_proposals,
        "native_plan_exact_route_hits": native_plan_exact_route_hits,
        "native_plan_expected_field_complete_hits": native_plan_expected_field_complete_hits,
        "native_plan_required_argument_gaps": native_plan_required_argument_gaps,
        "zero_score_exposed_cases": zero_score_exposed_cases,
        "by_language": by_language,
    }


def validate_expected_source_contracts(
    router: SchemaRouter,
    cases: tuple[SourceQueryCase, ...] = CASES,
) -> int:
    """Refuse a missing original publisher route or expected source field."""
    expected: dict[str, set[str]] = {}
    for case in cases:
        if case.expected_route is not None:
            expected.setdefault(case.expected_route, set()).update(case.expected_fields)
    for route_id, fields in expected.items():
        tool_key, separator, endpoint_name = route_id.partition(".")
        if not separator or tool_key not in router.registry.keys():
            raise ValueError("expected original source route missing")
        tool = router.registry.get(tool_key)
        if endpoint_name not in {endpoint.name for endpoint in tool.endpoints}:
            raise ValueError("expected original source endpoint missing")
        endpoint = tool.endpoint(endpoint_name)
        if not fields.issubset({field.name for field in endpoint.output_fields}):
            raise ValueError("original source field contract missing")
    return len(expected)


def evaluate_selection(
    router: SchemaRouter,
    *,
    cases: tuple[SourceQueryCase, ...] = CASES,
) -> dict[str, Any]:
    """Observe true unhinted native retrieval and planning; never invoke."""
    registry_version = router.registry.version
    rows: list[dict[str, Any]] = []
    for case in cases:
        # Do not pass any part of the answer label to the native engine.
        request = PlanRequest(query=case.query)
        retrieved = router.retrieve_executable(request, k=5)
        plan = router.plan_executable(request)
        if (
            retrieved.registry_version != registry_version
            or plan.registry_version != registry_version
        ):
            raise ValueError("native registry version changed during selection evaluation")
        candidates = [
            {"route_id": candidate.route_id, "score": candidate.score}
            for candidate in retrieved.candidates
        ]
        positive = [candidate for candidate in candidates if candidate["score"] > 0]
        first_call = plan.calls[0] if plan.calls else None
        row: dict[str, Any] = {
            "id": case.id,
            "language": case.language,
            "expected_route": case.expected_route,
            "candidates": candidates,
            "positive_top1_route": positive[0]["route_id"] if positive else None,
            "planned_route": f"{first_call.tool}.{first_call.endpoint}" if first_call else None,
            "planned_fields": list(first_call.fields) if first_call else [],
            "required_expected_fields": list(case.expected_fields),
            "missing_expected_fields": sorted(
                set(case.expected_fields) - set(first_call.fields if first_call else [])
            ),
            "missing_required_arguments": list(
                first_call.missing_required_arguments if first_call else []
            ),
            "plan_executable": plan.executable,
        }
        rows.append(row)
    return {
        "evidence_tier": "E0_NATIVE_RETRIEVAL_HOST_LABELS_NOT_E2",
        "live_source_discovery": False,
        "registry_tool_count": len(router.registry.keys()),
        "registry_version": registry_version,
        "source_contract_observation": True,
        "source_task_labels_are_host_authored": True,
        "model_calls": 0,
        "provider_invocations": 0,
        "default_ranking_changed": False,
        "independent_e2_gold": False,
        "rows": rows,
        "metrics": score_selection_report(rows),
    }


async def run_live_selection_e1() -> dict[str, Any]:
    """Discover original remote schemas; no selected endpoint is executed."""
    router = SchemaRouter(policy=ExecutionPolicy(allow_unclassified_remote=True))
    try:
        registration = await router.add_provider(
            "crossref",
            timeout=20,
            trusted_headers_by_method={
                "rest": {
                    "User-Agent": "SchemaRouter public route research (https://github.com/JDeun/SchemaRouter)"
                }
            },
        )
        if len(registration.registered_tool_keys) != 1:
            raise ValueError("original Crossref provider did not register")
        await router.add_url(COD_URL, kind="optimade", name="cod_public", timeout=20)
        await router.add_url(
            DEEPWIKI_URL,
            kind="mcp",
            name="deepwiki_public",
            timeout=25,
            mcp_client_factory=bounded_public_mcp_client_factory,
        )
        if set(router.registry.keys()) != {
            "crossref",
            "cod_public",
            "deepwiki_public",
        }:
            raise ValueError("unexpected mixed actual source registry")
        if validate_expected_source_contracts(router) != 3:
            raise ValueError("live original source route contracts incomplete")
        # E1 requires genuine COD+MCP remote discovery. Crossref's contract
        # remains a bundled source-authored profile, NOT newly discovered
        # remote metadata; the prior source matrix separately executed it.
        report = evaluate_selection(router)
        report["evidence_tier"] = "E1_LIVE_SOURCE_RETRIEVAL_HOST_LABELS_NOT_E2"
        report["live_source_discovery"] = True
        report["source_contract_provenance"] = live_source_contract_provenance()
        report["live_remote_schema_discovered_tool_count"] = 2
        return report
    finally:
        await router.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="opt in to actual public source discovery"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("external source discovery requires explicit --live")
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        report = asyncio.run(run_live_selection_e1())
    except Exception as exc:
        print(json.dumps({"status": "failure", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    finally:
        logging.disable(previous_logging_disable)
    print(json.dumps({"status": "success", **report}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
