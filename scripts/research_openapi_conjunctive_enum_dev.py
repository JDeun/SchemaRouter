"""Conjunctive OpenAPI field-contract *host oracle* over source-pinned E5 ranks.

Only reads current authorized CapabilityCandidate typed parameter schemas.
Neither user operation nor requested variables are inferred from language.
No remote tools, default model changes, classifier or real-agent calls.
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
    QUERIES,
    SOURCE_NAMES,
    UNSUPPORTED,
)
from scripts.research_openapi_authorized_enum_gate_dev import (
    REQUIREMENTS,
    conservative_selection,
    evaluate as original_evaluate,
    supports_requested_variable,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    catalog,
    validate_semantic_ranks,
)

ORIGINAL_ENUM_REPORT_SHA256 = (
    "e3945b0f8eba04370b0bec802dad36483c4ac9e249da6e57434318d829dcfbe1"
)
# Strictly preregistered *post-hoc DEV hypothesis*. Both marine variables
# appear explicitly in all three source-authored marine queries. Other
# categories retain the first experiment's single variable or abstention.
DEV_REQUIRED_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    **{
        source: ((requirement,) if requirement is not None else ())
        for source, requirement in REQUIREMENTS.items()
    },
    "marine": (
        ("hourly", "wave_height"),
        ("hourly", "ocean_current_velocity"),
    ),
}
MAX_REQUIREMENTS = 4


def validate_requirement_set(
    requirements: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    if (
        type(requirements) is not tuple
        or not 1 <= len(requirements) <= MAX_REQUIREMENTS
    ):
        raise ValueError("no approved bounded host field conjunction")
    seen: set[tuple[str, str]] = set()
    for item in requirements:
        if (
            type(item) is not tuple or len(item) != 2
            or any(
                type(v) is not str or not v or v != v.strip()
                or len(v) > 128 for v in item
            )
            or item in seen
        ):
            raise ValueError("invalid, duplicate or untrusted host field pair")
        seen.add(item)
    return requirements


def select_conjunctive(
    ranks: list[str],
    candidates: dict[str, Any],
    *,
    action: str,
    requirements: tuple[tuple[str, str], ...],
) -> tuple[str | None, str, list[str]]:
    """Select IFF exactly one approved endpoint satisfies *all* requirements."""
    if (
        len(ranks) != len(set(ranks))
        or set(ranks) != set(candidates)
        or not ranks
    ):
        raise ValueError("model rank not a full authorized candidate permutation")
    if action != "read":
        return None, "denied_action", []
    # Never convert missing/untrusted requirements to model Top1 fallback.
    if not requirements:
        return None, "no_host_requirement", []
    declared = validate_requirement_set(requirements)
    matched = [
        route for route in ranks
        if all(
            supports_requested_variable(
                candidates[route], action=action, parameter=p, variable=v,
            )
            for p, v in declared
        )
    ]
    if not matched:
        return None, "no_full_conjunction", []
    if len(matched) > 1:
        return None, "ambiguous_conjunction", matched
    return matched[0], "one_exact_conjunction", matched


def evaluate(
    manifest: Path,
    source_dir: Path,
    frozen_real_e5_report: Path,
    frozen_single_enum_report: Path,
) -> dict[str, Any]:
    old_bytes = frozen_single_enum_report.read_bytes()
    if hashlib.sha256(old_bytes).hexdigest() != ORIGINAL_ENUM_REPORT_SHA256:
        raise ValueError("frozen single-field baseline artifact bytes drifted")
    baseline = json.loads(old_bytes)
    # Recompute source-attested prior algorithm, fail if its per-case output
    # disagrees with frozen evidence. No gold route is used by select_conjunctive.
    recomputed = original_evaluate(
        manifest, source_dir, frozen_real_e5_report,
    )
    if (
        baseline.get("study") != recomputed["study"]
        or baseline.get("rows") != recomputed["rows"]
        or baseline.get("by_language") != recomputed["by_language"]
        or baseline.get("original_model_report_sha256") !=
            recomputed["original_model_report_sha256"]
    ):
        raise ValueError("frozen single-field baseline differs from this source")
    router, viewer, sources, publisher = catalog(manifest, source_dir)
    approved = {x for group in sources.values() for x in group}
    if len(approved) != 9 or set(DEV_REQUIRED_PAIRS) != set(SOURCE_NAMES):
        raise ValueError("publisher or host oracle identity drift")
    original_rows = {
        (x["source"], x["language"], x["kind"]): x
        for x in baseline["rows"] if x["source"] in SOURCE_NAMES
    }
    if len(original_rows) != 27:
        raise ValueError("missing full frozen original supported rows")

    comparison: list[dict[str, Any]] = []
    for src in SOURCE_NAMES:
        for lang, query in zip(LANGUAGES, QUERIES[src], strict=True):
            original = original_rows[(src, lang, "supported")]
            retrieved = router.retrieve_authorized(
                PlanRequest(query=query), principal=viewer, k=9,
            )
            candidates = {x.route_id: x for x in retrieved.candidates}
            validate_semantic_ranks(
                [x.route_id for x in retrieved.candidates], approved,
            )
            order = original["original_e5_top1"]
            # Fetch full model ranking directly from source-pinned report, not
            # from single-field's (possibly empty) eligible matches.
            # The original source-author E5 report identity is reverified by
            # original_evaluate() before using this report.
            real = __frozen_model_case(
                frozen_real_e5_report, src, lang, "supported",
            )
            ranks = real["ranked"]["original"]
            validate_semantic_ranks(ranks, approved)
            if ranks[0] != order:
                raise ValueError("model ranking/baseline source drift")
            required = DEV_REQUIRED_PAIRS[src]
            selected, reason, matches = select_conjunctive(
                ranks, candidates, action="read", requirements=required,
            )
            gold = sources[src][0]
            comparison.append({
                "source": src, "language": lang, "kind": "supported",
                "required_pairs": [list(pair) for pair in required],
                "model_top1": order,
                "baseline_selected": original["selected"],
                "baseline_reason": original["reason"],
                "selected": selected, "reason": reason,
                "eligible": matches,
                "gold": gold,
                "correct": selected == gold,
                "wrong_selected": selected is not None and selected != gold,
                "no_execution": True,
            })
    # Negative queries + tougher deceptive writes with genuine variables.
    for name, *questions in UNSUPPORTED:
        for lang, query in zip(LANGUAGES, questions, strict=True):
            retrieved = router.retrieve_authorized(
                PlanRequest(query=query), principal=viewer, k=9,
            )
            candidates = {x.route_id: x for x in retrieved.candidates}
            validate_semantic_ranks(list(candidates), approved)
            selected, reason, matches = select_conjunctive(
                list(candidates), candidates, action="write",
                requirements=(("hourly", "temperature_2m"),),
            )
            comparison.append({
                "source": name, "language": lang, "kind": "unsupported",
                "action": "write", "selected": selected, "reason": reason,
                "eligible": matches, "no_execution": True,
            })
    for lang in LANGUAGES:
        retrieved = router.retrieve_authorized(
            PlanRequest(query=QUERIES["marine"][LANGUAGES.index(lang)]),
            principal=viewer, k=9,
        )
        candidates = {x.route_id: x for x in retrieved.candidates}
        validate_semantic_ranks(list(candidates), approved)
        selected, reason, matches = select_conjunctive(
            list(candidates), candidates, action="write",
            requirements=DEV_REQUIRED_PAIRS["marine"],
        )
        comparison.append({
            "source": "deceptive-marine-mutation", "language": lang,
            "kind": "unsupported", "action": "write",
            "selected": selected, "reason": reason, "eligible": matches,
            "no_execution": True,
        })
    if len(comparison) != 39:
        raise ValueError("not 39 predeclared source-bound case outcomes")
    counts = {}
    for lang in (*LANGUAGES, "all"):
        yes = [
            x for x in comparison if x["kind"] == "supported"
            and (lang == "all" or x["language"] == lang)
        ]
        no = [
            x for x in comparison if x["kind"] == "unsupported"
            and (lang == "all" or x["language"] == lang)
        ]
        counts[lang] = {
            "supported": len(yes),
            "original_e5_top1_correct": sum(
                x["model_top1"] == x["gold"] for x in yes
            ),
            "single_enum_unique_correct": sum(
                x["baseline_selected"] == x["gold"] for x in yes
            ),
            "conjunction_unique_correct": sum(x["correct"] for x in yes),
            "conjunction_unique_wrong": sum(x["wrong_selected"] for x in yes),
            "conjunction_abstained": sum(x["selected"] is None for x in yes),
            "unsupported": len(no),
            "unsupported_selected": sum(
                x["selected"] is not None for x in no
            ),
            "reasons": dict(Counter(x["reason"] for x in yes)),
        }
    if (
        counts["all"]["supported"] != 27
        or counts["all"]["unsupported"] != 12
        or counts["all"]["unsupported_selected"] != 0
    ):
        raise ValueError("negative source-authored action was not denied")
    return {
        "schema_version": 1,
        "study": "real_provider_authorized_conjunctive_enum_oracle_dev",
        "original_single_enum_sha256": ORIGINAL_ENUM_REPORT_SHA256,
        "original_real_e5_sha256": recomputed[
            "original_model_report_sha256"
        ],
        "provider_source_sha256": {
            name: publisher[name]["sha256"] for name in SOURCE_NAMES
        },
        "source_author_requirement_set": {
            name: [list(pair) for pair in pairs]
            for name, pairs in DEV_REQUIRED_PAIRS.items()
        },
        "rows": comparison,
        "by_language": counts,
        "scope": {
            "real_publisher_contracts": True,
            "actual_source_pinned_e5_rankings": True,
            "manually_supplied_host_operation_field_oracle": True,
            "queries_previously_exposed_dev": True,
            "no_independent_user_intent_inference": True,
            "no_actual_provider_or_agent_execution": True,
            "no_calibrated_no_fit": True,
            "no_real_host_authentication": True,
            "may_release": False,
        },
    }


def __frozen_model_case(
    path: Path, source: str, language: str, kind: str,
) -> dict[str, Any]:
    # Checked against pinned SHA and per-case identities by the original
    # source_report() inside original_evaluate().
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        c for c in data["cases"]
        if (c["source"], c["language"], c["kind"]) ==
        (source, language, kind)
    ]
    if len(matches) != 1:
        raise ValueError("missing or duplicated original E5 rank")
    return matches[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--source-dir", type=Path, required=True)
    ap.add_argument("--frozen-e5-report", type=Path, required=True)
    ap.add_argument("--frozen-single-enum", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = evaluate(
        args.manifest, args.source_dir,
        args.frozen_e5_report, args.frozen_single_enum,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": result["study"], "metrics": result["by_language"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
