"""E0 paired lexical-vs-declared-concept *existing agent* DEV comparison.

Source owner declares the ontology BEFORE the evaluator sees the tasks.
No scoring gold, expected route or execution state reaches either selector.
No new model/agent/host executor, and no independent E2 claim.
"""
from __future__ import annotations

import re
import statistics
from collections.abc import Callable
from typing import Any

from schemarouter import (
    NativeConceptCatalog,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedConceptFixed5Selector,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    _visible_fingerprints,
)

ARMS = ("lexical_k5", "declared_concepts_k5")
EVIDENCE = "E0_SCRIPTED_DEV_NOT_INDEPENDENT"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_TASKS = 24
MAX_ROUTES = 500
FIXED_K = 5


def _lexical_selector(
    view: AuthorizedAgentToolSurface,
) -> Callable[[str, tuple[str, ...]], list[str]]:
    """Baseline: unmodified production ranking on the identical scoped source."""
    pinned = _visible_fingerprints(view)

    def select(query: str, offered: tuple[str, ...]) -> list[str]:
        view.assert_source_unchanged()
        if (
            query != view.original_query
            or type(offered) is not tuple
            or offered != view.visible_route_ids
            or pinned != _visible_fingerprints(view)
        ):
            raise PolicyViolationError("lexical source and principal drift")
        result = view.router.retrieve_authorized(
            query, principal=view._principal, k=FIXED_K,
        )
        view.assert_source_unchanged()
        names = [candidate.route_id for candidate in result.candidates]
        if (
            result.registry_version != view.witness[1]
            or len(names) > FIXED_K
            or len(names) != len(set(names))
            or not set(names).issubset(offered)
            or any(
                (candidate.tool_fingerprint, candidate.endpoint_fingerprint)
                != pinned[candidate.route_id]
                for candidate in result.candidates
            )
            or pinned != _visible_fingerprints(view)
        ):
            raise PolicyViolationError("lexical baseline not native source-pinned")
        return names

    return select


def _validate_tasks(tasks: tuple[dict[str, Any], ...]) -> None:
    if type(tasks) is not tuple or not 1 <= len(tasks) <= MAX_TASKS:
        raise ValueError("invalid bounded paired E0 case count")
    names: set[str] = set()
    for task in tasks:
        if (
            type(task) is not dict
            or type(task.get("semantic_task_id")) is not str
            or not 1 <= len(task["semantic_task_id"]) <= 160
            or task["semantic_task_id"] in names
            or type(task.get("query")) is not str
            or not 2 <= len(task["query"].encode("utf-8")) <= 512
            or task.get("language") not in ("en", "ko", "ja")
            or type(task.get("supported")) is not bool
            or type(task.get("required_routes")) is not list
            or type(task.get("executor_fixture")) is not dict
        ):
            raise ValueError("invalid paired E0 case identity or grading contract")
        names.add(task["semantic_task_id"])


def _safe_measures(row: dict[str, Any]) -> dict[str, Any]:
    """Allowlisted view output; never return raw source/agent text or gold."""
    if (
        type(row) is not dict
        or type(row.get("passed")) is not bool
        or type(row.get("task_complete")) is not bool
        or type(row.get("visible_candidate_counts")) is not list
        or len(row["visible_candidate_counts"]) != 1
        or type(row["visible_candidate_counts"][0]) is not int
        or not 0 <= row["visible_candidate_counts"][0] <= FIXED_K
        or type(row.get("unauthorized_destructive_executions")) is not int
        or row["unauthorized_destructive_executions"] != 0
    ):
        raise PolicyViolationError("untrusted or unsafe paired E0 outcome")
    allowed = {}
    for name in (
        "input_tokens", "tool_schema_tokens", "tool_call_count",
        "candidate_selection_latency_ms", "episode_wall_latency_ms",
    ):
        val = row.get(name)
        if (
            type(val) not in (int, float)
            or val < 0
            or not float("-inf") < val < float("inf")
        ):
            raise ValueError("invalid paired E0 numeric telemetry")
        allowed[name] = float(val)
    return {
        "passed": row["passed"],
        "task_complete": row["task_complete"],
        "candidate_count": row["visible_candidate_counts"][0],
        **allowed,
    }


def run_paired_concept_agent_e0(
    router: SchemaRouter,
    *,
    catalog: NativeConceptCatalog,
    tasks: tuple[dict[str, Any], ...],
    principal: PrincipalContext,
    agent_factory: Callable[[], Any],
    source_revision: str,
) -> dict[str, Any]:
    """Same frozen source/principal+K5, fresh agents, original evaluator.

    Task fixture + gold are supplied ONLY to the original trusted grader
    after candidate selection, never to either callback, selector or model.
    Independent publisher-authored source and agent quality are NOT implied
    by validated shapes or self-reported revision.
    """
    if (
        not isinstance(router, SchemaRouter)
        or not isinstance(catalog, NativeConceptCatalog)
        or not isinstance(principal, PrincipalContext)
        or not callable(agent_factory)
        or type(source_revision) is not str
        or not SHA40.fullmatch(source_revision)
    ):
        raise ValueError("invalid trusted paired experiment context")
    _validate_tasks(tasks)
    # Reject mutated source-owner ontology *before* any model interaction.
    NativeConceptCatalog.model_validate(
        catalog.model_dump(mode="python"), strict=True,
    )
    original_witness = router._retrieval_authority_witness()
    counts: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    paired_results: list[tuple[bool, bool]] = []
    language_counts: dict[str, dict[str, dict[str, int]]] = {
        lang: {arm: {"passed": 0, "tasks": 0} for arm in ARMS}
        for lang in ("en", "ko", "ja")
    }
    supported_counts: dict[str, dict[str, int]] = {
        arm: {"supported_pass": 0, "supported_tasks": 0,
              "unsupported_no_call_pass": 0, "unsupported_tasks": 0}
        for arm in ARMS
    }

    for task in tasks:
        observed: dict[str, bool] = {}
        source_ids_before: tuple[str, ...] | None = None
        fingerprints_before: dict[str, tuple[str, str]] | None = None
        # No task gold or expected route is inspected in either callback.
        # Both conditions use the same original query and the same registry.
        for arm in ARMS:
            router._check_retrieval_authority_witness(original_witness)
            view = capture_authorized_agent_tool_surface(
                router, task["query"], principal=principal,
                max_registered_routes=MAX_ROUTES,
            )
            visible_ids = view.visible_route_ids
            pins = _visible_fingerprints(view)
            if source_ids_before is None:
                source_ids_before = visible_ids
                fingerprints_before = pins
            elif visible_ids != source_ids_before or pins != fingerprints_before:
                raise PolicyViolationError("paired source differs between arms")

            selector = (
                _lexical_selector(view)
                if arm == "lexical_k5"
                else AuthorizedConceptFixed5Selector(view, catalog)
            )
            agent = agent_factory()
            row = run_generated_episode(
                agent, router.registry, task,
                EXPERIMENTAL_FIXED5_CONDITION,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
            )
            view.assert_source_unchanged()
            router._check_retrieval_authority_witness(original_witness)
            measure = _safe_measures(row)
            counts[arm].append(measure)
            observed[arm] = measure["passed"]
            language_counts[task["language"]][arm]["tasks"] += 1
            language_counts[task["language"]][arm]["passed"] += int(measure["passed"])
            bucket = supported_counts[arm]
            if task["supported"]:
                bucket["supported_tasks"] += 1
                bucket["supported_pass"] += int(measure["passed"])
            else:
                bucket["unsupported_tasks"] += 1
                bucket["unsupported_no_call_pass"] += int(measure["passed"])

        paired_results.append((
            observed["lexical_k5"], observed["declared_concepts_k5"],
        ))

    output: dict[str, Any] = {}
    for arm in ARMS:
        values = counts[arm]
        output[arm] = {
            "cases": len(values),
            "scripted_fixture_pass": sum(v["passed"] for v in values),
            **supported_counts[arm],
            "mean_visible_candidate_count": statistics.fmean(
                v["candidate_count"] for v in values
            ),
            "mean_input_tokens": statistics.fmean(
                v["input_tokens"] for v in values
            ),
            "mean_tool_schema_tokens": statistics.fmean(
                v["tool_schema_tokens"] for v in values
            ),
            "mean_candidate_selection_latency_ms": statistics.fmean(
                v["candidate_selection_latency_ms"] for v in values
            ),
            "mean_episode_wall_latency_ms": statistics.fmean(
                v["episode_wall_latency_ms"] for v in values
            ),
        }

    router._check_retrieval_authority_witness(original_witness)
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "publication_gate_passed": False,
        "source_revision_self_reported": source_revision,
        "strict_k": FIXED_K,
        "paired_tasks": len(tasks),
        "arms": list(ARMS),
        "metrics": output,
        "paired_scripted_win_concept": sum(not a and b for a, b in paired_results),
        "paired_scripted_win_lexical": sum(a and not b for a, b in paired_results),
        "paired_scripted_ties": sum(a == b for a, b in paired_results),
        "languages": language_counts,
        "limitations": (
            "Synthetic developer-authored task/ontology and scripted agent",
            "No independent publisher cohort or calibrated unsupported verdict",
            "FrozenCorpusExecutor fixture is not native provider execution",
            "No real agent model, real final-answer correctness or E2 claims",
            "Input provenance is self-reported; no signature or external attestation",
        ),
    }
