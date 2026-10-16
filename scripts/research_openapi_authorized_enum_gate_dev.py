"""Fail-closed *host-oracle* typed variable gate over real E5 DEV Top-9.

Host-provided request requirements are *manually authored* from an exposed
development cohort. They are not a query intent model, authenticated host
input, independent evaluation, or production permission. Real published
OpenAPI enum contracts, however, are used without manual endpoint features.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from schemarouter import PlanRequest
from scripts.research_open_meteo_real_openapi_dev import (
    LANGUAGES,
    SOURCE_NAMES,
    UNSUPPORTED,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    catalog,
    validate_semantic_ranks,
)

REPORT_SHA256 = "b8fc826397c0385d2b59b5968d3b7f53a2433f7327a8a3679168ecb7127ff038"
SOURCE_RUN_ID = 38863136350
SOURCE_COMMIT = "1dae94238bb2dd5dca18a7a48d29e322ca35ae3e"
# Same-author supplied request-variable oracle, NOT extracted from query.
# These variables are from the provider's published selection vocabulary,
# but the intended one is inferred manually by the research author.
REQUIREMENTS: dict[str, tuple[str, str] | None] = {
    "air-quality": ("hourly", "pm2_5"),
    "climate": ("daily", "temperature_2m_mean"),
    "elevation": None,
    "ensemble": ("hourly", "temperature_2m"),
    "flood": ("daily", "river_discharge"),
    "forecast": ("hourly", "temperature_2m"),
    "historical-weather": ("hourly", "temperature_2m"),
    "marine": ("hourly", "wave_height"),
    "seasonal": ("monthly", "temperature_2m_mean"),
}
NEGATIVE_KINDS = ("delete", "transfer", "purchase")


def source_report(path: Path) -> tuple[dict[str, Any], str]:
    blob = path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    if sha != REPORT_SHA256:
        raise ValueError("original model ablation report bytes drifted")
    d = json.loads(blob)
    if (
        d.get("study") != "real_provider_authorized_e5_contract_text_ablation_dev"
        or d.get("repository_commit") != SOURCE_COMMIT
        or d.get("model_id") != MODEL_ID
        or d.get("pinned_model_revision") != MODEL_REVISION
        or d.get("actual_cases") != 36
        or d.get("expected_cases") != 36
        or d.get("scope", {}).get("may_release") is not False
        or set(d.get("variants", [])) != {
            "original", "parameter_names", "parameter_descriptions"
        }
    ):
        raise ValueError("untrusted model source report identity")
    return d, sha


def supports_requested_variable(
    candidate: Any,
    *,
    action: str,
    parameter: str | None,
    variable: str | None,
) -> bool:
    """Check only *already authorized* typed endpoint metadata.

    Without a fully specified host requirement, no route is accepted.
    Unknown action or unrecognized parameter/enum fails closed.
    """
    if action != "read" or candidate.read_only is not True:
        return False
    if (
        not isinstance(parameter, str) or not parameter
        or not isinstance(variable, str) or not variable
    ):
        return False
    for item in candidate.parameters:
        if item.name != parameter or item.location != "query":
            continue
        schema = item.json_schema
        if not isinstance(schema, dict):
            continue
        allowed = schema.get("enum")
        if schema.get("type") == "array":
            child = schema.get("items")
            allowed = child.get("enum") if isinstance(child, dict) else None
        if (
            isinstance(allowed, list)
            and all(isinstance(x, str) for x in allowed)
            and variable in allowed
        ):
            return True
    return False


def conservative_selection(
    ranks: list[str],
    candidates: dict[str, Any],
    *,
    action: str,
    requirement: tuple[str, str] | None,
) -> tuple[str | None, str, list[str]]:
    if len(ranks) != len(set(ranks)) or set(ranks) != set(candidates):
        raise ValueError("source E5 ranking cannot add/drop authorized routes")
    param, var = requirement if requirement is not None else (None, None)
    matching = [
        route for route in ranks
        if supports_requested_variable(
            candidates[route], action=action,
            parameter=param, variable=var,
        )
    ]
    if not matching:
        return None, "no_exact_enum_or_denied_operation", []
    if len(matching) != 1:
        return None, "ambiguous_exact_enum", matching
    return matching[0], "one_exact_declared_enum", matching


def evaluate(
    manifest: Path,
    source_dir: Path,
    report_file: Path,
) -> dict[str, Any]:
    report, source_sha = source_report(report_file)
    router, viewer, source_routes, provider = catalog(manifest, source_dir)
    authorized = {
        route for routes in source_routes.values() for route in routes
    }
    if len(authorized) != 9 or set(REQUIREMENTS) != set(SOURCE_NAMES):
        raise ValueError("unregistered provider/request variable contract")
    all_cases = report["cases"]
    if not isinstance(all_cases, list) or len(all_cases) != 36:
        raise ValueError("incomplete real E5 rows")
    expected_keys = {
        (name, language, "supported")
        for name in SOURCE_NAMES for language in LANGUAGES
    } | {
        (name, language, "unsupported")
        for name in NEGATIVE_KINDS for language in LANGUAGES
    }
    observed_keys: set[tuple[str, str, str]] = set()
    results: list[dict[str, Any]] = []
    for case in all_cases:
        source, language, kind = (
            case.get("source"), case.get("language"), case.get("kind")
        )
        key = (source, language, kind)
        if key not in expected_keys or key in observed_keys:
            raise ValueError("unsupported/duplicated source-authored E5 case")
        observed_keys.add(key)
        if case.get("tool_executed") is not False:
            raise ValueError("source ablation was not read-only")
        # Read actual currently authorized schema surface with principal;
        # never read a registry-wide contract to decide routing.
        lexical = router.retrieve_authorized(
            PlanRequest(query=(
                __query_for_dev_case(source, language, kind)
            )), principal=viewer, k=9,
        )
        candidates = {
            item.route_id: item for item in lexical.candidates
        }
        validate_semantic_ranks(
            [c.route_id for c in lexical.candidates], authorized,
        )
        for variant in ("original", "parameter_names", "parameter_descriptions"):
            ranks = case.get("ranked", {}).get(variant)
            if not isinstance(ranks, list):
                raise ValueError("missing exact source E5 Top9")
            validate_semantic_ranks(ranks, authorized)
        ranking = case["ranked"]["original"]
        if kind == "supported":
            request = REQUIREMENTS[source]
            action = "read"
            gold = source_routes[source][0]
        else:
            request = ("hourly", "temperature_2m")
            action = "write" if source in ("delete", "purchase") else "transfer"
            gold = None
        candidate, reason, matching = conservative_selection(
            ranking, candidates, action=action, requirement=request,
        )
        results.append({
            "source": source,
            "language": language,
            "kind": kind,
            "author_oracle_action": action,
            "author_oracle_parameter_variable": list(request)
                if request is not None else None,
            "original_e5_top1": ranking[0],
            "original_e5_correct": ranking[0] == gold if gold else None,
            "selected": candidate,
            "reason": reason,
            "eligible_count": len(matching),
            "eligible_ranked_ids": matching,
            "gold": gold,
            "gate_correct": candidate == gold if gold else None,
            "no_tool_executed": True,
        })
    if observed_keys != expected_keys or len(results) != 36:
        raise ValueError("missing pinned model DEV rows")
    # Add deceptive negative where unsupported mutation asks for the
    # *valid* forecast variable. Presence of a variable is NOT permission.
    for language in LANGUAGES:
        query = __query_for_dev_case("forecast", language, "supported")
        candidate_set = router.retrieve_authorized(
            PlanRequest(query=query), principal=viewer, k=9,
        ).candidates
        mapping = {c.route_id: c for c in candidate_set}
        candidate, reason, matching = conservative_selection(
            sorted(mapping), mapping, action="write",
            requirement=("hourly", "temperature_2m"),
        )
        if candidate is not None or matching:
            raise ValueError("write action authorized by read-only enum")
        results.append({
            "source": "deceptive-write-same-variable",
            "language": language,
            "kind": "unsupported",
            "author_oracle_action": "write",
            "author_oracle_parameter_variable": [
                "hourly", "temperature_2m"
            ],
            "selected": candidate, "reason": reason,
            "eligible_count": 0, "eligible_ranked_ids": [],
            "no_tool_executed": True,
        })
    breakdown = {}
    for lang in (*LANGUAGES, "all"):
        supported = [
            r for r in results if r["kind"] == "supported"
            and (lang == "all" or r["language"] == lang)
        ]
        negative = [
            r for r in results if r["kind"] == "unsupported"
            and (lang == "all" or r["language"] == lang)
        ]
        breakdown[lang] = {
            "supported": len(supported),
            "original_e5_top1_correct": sum(
                r["original_e5_correct"] for r in supported
            ),
            "gated_unique_correct": sum(
                r["gate_correct"] for r in supported
            ),
            "gated_unique_wrong": sum(
                r["selected"] is not None and not r["gate_correct"]
                for r in supported
            ),
            "gated_ambiguous": sum(
                r["reason"] == "ambiguous_exact_enum" for r in supported
            ),
            "gated_missing_or_denied": sum(
                r["reason"] == "no_exact_enum_or_denied_operation"
                for r in supported
            ),
            "negative": len(negative),
            "negative_selected": sum(
                r["selected"] is not None for r in negative
            ),
            "reasons": dict(Counter(r["reason"] for r in supported)),
        }
    if len(results) != 39 or breakdown["all"]["negative_selected"]:
        raise ValueError("incomplete / failed fail-closed request matrix")
    return {
        "schema_version": 1,
        "study": "external_openapi_authorized_enum_host_oracle_dev",
        "original_model_report_sha256": source_sha,
        "original_model_run_id": SOURCE_RUN_ID,
        "model_revision": MODEL_REVISION,
        "source_repo_commit": report["repository_commit"],
        "provider_manifest_sha256": hashlib.sha256(
            manifest.read_bytes()
        ).hexdigest(),
        "provider_source_sha256": {
            name: provider[name]["sha256"] for name in SOURCE_NAMES
        },
        "author_oracle_requirements": {
            name: list(value) if value else None
            for name, value in REQUIREMENTS.items()
        },
        "rows": results, "by_language": breakdown,
        "scope": {
            "actual_published_provider_contracts": True,
            "actual_original_e5_candidate_rankings": True,
            "request_action_and_variable_are_manual_oracles": True,
            "query_classifier_evaluated": False,
            "author_seen_dev": True,
            "principal_authenticated_by_real_host": False,
            "provider_endpoint_executed": False,
            "agent_success_evaluated": False,
            "no_fit_independently_calibrated": False,
            "no_default_change": True,
            "may_release": False,
        },
    }


def __query_for_dev_case(source: str, language: str, kind: str) -> str:
    from scripts.research_open_meteo_real_openapi_dev import (
        QUERIES,
    )
    index = LANGUAGES.index(language)
    if kind == "supported":
        return QUERIES[source][index]
    return next(
        queries[index] for name, *queries in UNSUPPORTED
        if name == source
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--frozen-e5-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.manifest, args.source_dir, args.frozen_e5_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": result["study"],
        "groups": result["by_language"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
