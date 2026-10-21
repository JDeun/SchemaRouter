"""Paired real-agent G5 DEV on six disclosed local synthetic fixture tasks.

Reuses run_generated_episode/FrozenCorpusExecutor, current principal-scoped
model-visible source capture and the typed G5 real E5 fixed-K5 ranker.
No original provider request, agent factual oracle, publisher gold or E2 claim.
"""
from __future__ import annotations

import argparse
import json
import platform
import secrets
import subprocess
from pathlib import Path
from typing import Any

from schemarouter import InMemoryRegistry, NativeDeclaredFieldGroup
from schemarouter.decisions import (
    CallableDecisionBackend,
    DecisionBackend,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME as AGENT_MODEL_ID,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_REVISION as AGENT_MODEL_REVISION,
)
from scripts.agent_utility_v7_dev_agent import SEED
from scripts.evaluate_agent_utility_phase_b_smollm3 import _parse_tool_calls
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_ID as E5_MODEL_ID,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_REVISION as E5_MODEL_REVISION,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import real_cpu_backend
from scripts.research_agent_stage_evidence_e0 import E0TraceProvenance
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)
from scripts.research_g5_decision_backend_ranker_e0 import (
    ResearchAuthorizedG5DecisionRanker,
)
from scripts.research_g5_e5_overflow_cpu_dev import (
    ACTOR,
    OOD,
    QUERIES,
    SERVICE_NAMES,
    _source,
)

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("source_first5", "e5_fixed5")
ACCOUNT_ID = "acct_demo_7"
FIXTURE_EVIDENCE = "E0_G5_PINNED_QWEN_E5_FIXTURE_DEV_NOT_E2"
INJECTED_EVIDENCE = "E0_G5_INJECTED_AGENT_AND_BACKEND_DEV_ONLY"
SYSTEM_PROMPT = (
    "You are a tool-using agent. If the appropriate supplied tool is present, "
    "call it with account_id from the user request using one "
    "<tool_call>{\"name\":\"service__read\",\"arguments\":"
    "{\"account_id\":\"...\"}}</tool_call>. Wait for the observation. "
    "Only call a listed tool. If the request cannot be answered by any listed "
    "tool, respond exactly REQUEST_MORE_TOOLS. After a successful tool call, "
    "respond with a short final answer. Never invent a tool or parameter."
)
# Control intentionally preserves the historical non-existent example tool
# name. Treatment is grounded in the actual provided tool inventory and
# discloses neither task gold nor an unregistered/forbidden route.
GROUNDED_PROMPT = (
    "You are a tool-using research agent. Solve the user's request using "
    "only the tools currently provided. Never invent a tool name, a source "
    "capability, or an argument. For each call copy the exact tool name "
    "from the supplied function list and use the supplied JSON argument "
    "schema. Issue at most one tool call, then wait for the observation. "
    "If no provided tool can answer the user's request, respond with "
    "exactly REQUEST_MORE_TOOLS. If an observation confirms that the "
    "request is complete, respond with a short final answer."
)
PROMPT_ARMS = ("legacy_unregistered_example", "grounded_inventory_only")


# One supported task per language, one unsupported task per language.
# Named route gold is scorer-only and is NOT passed to the selector or agent.
SLICES = ((0, "en"), (1, "ko"), (2, "ja"))


def _cases() -> list[tuple[str, str, str | None]]:
    cases = []
    for index, language in SLICES:
        service, en, ko, ja = QUERIES[index]
        selected = {"en": en, "ko": ko, "ja": ja}[language]
        cases.append((
            language, f"{selected} for account {ACCOUNT_ID}",
            f"service_{service}.read",
        ))
    cases.extend((language, query, None) for language, query in OOD)
    return cases


def _first_five(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def _candidate_selector(
    view: AuthorizedAgentToolSurface,
    graph: Any,
    required: NativeDeclaredFieldGroup,
    ranker: ResearchAuthorizedG5DecisionRanker,
    *,
    ranked_receipt: list[tuple[str, ...]] | None = None,
):
    def select(query: str, offered: tuple[str, ...]) -> list[str]:
        view.assert_source_unchanged()
        if query != view.original_query or offered != view.visible_route_ids:
            raise ValueError("G5 agent authorized source query/route drift")
        result = graph.lookup(
            view.router, query,
            group=required, principal=ACTOR, _research_ranker=ranker,
        )
        view.assert_source_unchanged()
        if (
            result.status != "ranked_unverified"
            or result.qualified_path_count != len(SERVICE_NAMES)
            or len(result.candidates) != 5
            or result.executable_authority
            or result.independent_quality_evidence
            or result.calibrated_no_fit
        ):
            raise ValueError("G5 E0 agent cannot use unproven ranked path")
        names = [candidate.consumer_route_id for candidate in result.candidates]
        if len(set(names)) != 5 or not set(names).issubset(offered):
            raise ValueError("G5 E0 agent rank escaped principal-scoped tool view")
        if ranked_receipt is not None:
            if ranked_receipt:
                raise ValueError("G5 E0 selector invoked more than once per episode")
            # Private to the evaluator; never returned as a model-side receipt.
            ranked_receipt.append(tuple(names))
        return names

    return select


class GraderOnlyAttemptObserver:
    """Unmodified generated turns; keep only route names transiently in memory.

    The same frozen parser used by the original executor is reused here.
    Gold/expected tool names never enter generate(). Raw generations and tool
    arguments are NOT retained or included in any published report.
    """

    def __init__(self, agent: Any) -> None:
        self.agent = agent
        self.attempted: list[str] = []
        self.first_visible_tools: tuple[str, ...] | None = None

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        actual_names = tuple(
            str(item["name"]).replace("__", ".", 1)
            for item in tools
        )
        if self.first_visible_tools is None:
            self.first_visible_tools = actual_names
        elif self.first_visible_tools != actual_names:
            raise ValueError("E0 model-visible source changed between turns")
        result = self.agent.generate(messages, tools)
        if result.get("context_overflow") is not True:
            try:
                calls = _parse_tool_calls(str(result["text"]))
            except Exception:  # noqa: BLE001
                # The original executor also records malformed calls as zero
                # attempts. Do not classify unsupported malformed output as
                # a successful no-fit refusal.
                calls = []
            self.attempted.extend(
                str(call["name"]).replace("__", ".", 1)
                for call in calls
            )
        return result


def _private_rank_diagnostic(
    *,
    ranked: tuple[str, ...],
    model_visible: tuple[str, ...],
    attempted: list[str],
    gold: str | None,
    observed_count: int,
) -> dict[str, Any]:
    """Only score ordered positions after executor completion, never tool IDs."""
    if (
        len(ranked) != 5 or len(set(ranked)) != 5
        or model_visible != tuple(sorted(ranked))
        or len(attempted) != observed_count
        or any(type(item) is not str for item in attempted)
    ):
        raise ValueError("invalid private G5 ranked/model-visible attempt witness")
    first = attempted[0] if attempted else None
    return {
        "expected_rank_in_selector_order": (
            ranked.index(gold) + 1
            if gold is not None and gold in ranked else None
        ),
        "first_attempt_rank_in_selector_order": (
            ranked.index(first) + 1
            if first is not None and first in ranked else None
        ),
        "first_attempt_slot_in_model_visible_order": (
            model_visible.index(first) + 1
            if first is not None and first in model_visible else None
        ),
        "first_attempt_was_expected_operation": (
            first == gold if first is not None and gold is not None else None
        ),
        "first_attempt_outside_top5": (
            first is not None and first not in ranked
        ),
    }


def run_fixture(
    backend: DecisionBackend,
    agent: Any,
    *,
    source_revision: str,
    system_prompt: str = SYSTEM_PROMPT,
    source_arms: tuple[str, ...] = ARMS,
    omit_identical_descriptions: bool = False,
) -> dict[str, Any]:
    # Injected model instances can NEVER self-attest as real inference.
    # Only the CLI that constructs both locally pinned runtimes may mark
    # the completed report as true real-model DEV.
    if (
        type(source_revision) is not str
        or len(source_revision) != 40
        or any(c not in "0123456789abcdef" for c in source_revision)
        or system_prompt not in (SYSTEM_PROMPT, GROUNDED_PROMPT)
        or type(source_arms) is not tuple
        or source_arms not in (ARMS, ("e5_fixed5",))
        or type(omit_identical_descriptions) is not bool
        or (omit_identical_descriptions and source_arms != ("e5_fixed5",))
        or (omit_identical_descriptions and system_prompt != GROUNDED_PROMPT)
    ):
        raise ValueError("invalid E0 source/model provenance")
    router, graph, concept = _source()
    registry = router.registry
    if not isinstance(registry, InMemoryRegistry):
        raise ValueError("G5 fixture requires frozen in-memory source executor")
    cases = _cases()
    if len(cases) != 6 or len(SERVICE_NAMES) != 24:
        raise ValueError("invalid synthetic G5 agent cohort")
    provenance = E0TraceProvenance(
        source_revision=source_revision,
        source_sha256=graph.field_index.snapshot_id,
        hmac_key=secrets.token_bytes(32), seed=SEED,
    )
    stats = {
        arm: {
            lang: {
                "supported_count": 0,
                "supported_fixture_completed": 0,
                "supported_required_route_visible": 0,
                "supported_tool_call_attempted": 0,
                "supported_wrong_operation_observed": 0,
                "supported_schema_rejection_observed": 0,
                "supported_argument_mismatch_observed": 0,
                "supported_completed_with_final_turn": 0,
                "unsupported_count": 0,
                "unsupported_strict_no_call": 0,
                "unsupported_no_call": 0,
                "unsupported_terminal_mismatch": 0,
                "unsupported_tool_calls": 0,
                "policy_blocks": 0,
                "stage_counts": {},
                "candidate_selection_ms": [],
                "episode_ms": [],
                "input_tokens": 0,
                "schema_tokens": 0,
            }
            for lang in ("en", "ko", "ja")
        }
        for arm in source_arms
    }
    private_rank_by_arm: dict[str, dict[str, dict[str, Any]]] = {
        arm: {} for arm in source_arms
    }
    # Same declared query, current native source and actor per paired arm;
    # alternating arm order guards part of model warmup order bias.
    for idx, (lang, query, gold) in enumerate(cases):
        task = {
            "semantic_task_id": f"g5-synthetic-fixture-{idx}",
            "task_stratum": (
                "supported_one_step" if gold is not None else "unsupported_no_fit"
            ),
            "language": lang,
            "query": query,
            "supported": gold is not None,
            "required_routes": [gold] if gold is not None else [],
            "executor_fixture": {
                "steps": [{
                    "route_id": gold,
                    "argument_rules": {"account_id": {"eq": ACCOUNT_ID}},
                    "observation": {"status": "ok"},
                }] if gold is not None else [],
            },
        }
        field_group = NativeDeclaredFieldGroup(
            aliases=(query,), required_fields=concept.required_fields,
            source_type=concept.source_type, license=concept.license,
        )
        for arm in (
            source_arms if idx % 2 == 0 else source_arms[::-1]
        ):
            view = capture_authorized_agent_tool_surface(
                router, query, principal=ACTOR,
            )
            if len(view.visible_route_ids) != len(SERVICE_NAMES) + 1:
                raise ValueError("G5 agent model-visible source incomplete")
            adapter = ResearchAuthorizedG5DecisionRanker(
                CallableDecisionBackend(_first_five)
                if arm == "source_first5" else backend,
                omit_identical_descriptions=omit_identical_descriptions,
            )
            receipt: list[tuple[str, ...]] = []
            selected = _candidate_selector(
                view, graph, field_group, adapter,
                ranked_receipt=receipt,
            )
            observed_agent = GraderOnlyAttemptObserver(agent)
            row = run_generated_episode(
                observed_agent, registry, task, EXPERIMENTAL_FIXED5_CONDITION,
                system_prompt=system_prompt,
                experimental_candidate_selector=selected,
                experimental_agent_tool_surface=view,
                experimental_e0_trace_provenance=provenance,
                experimental_block_unavailable_observation=True,
            )
            if (
                row.get("independent_quality_evidence") is not False
                or row.get("executable_authority") is not False
                or type(row.get("e0_stage_evidence")) is not dict
                or row["e0_stage_evidence"].get("independent_e2_qualified")
                is not False
            ):
                raise ValueError("G5 agent E0 trace changed evidence authority")
            if len(receipt) != 1 or observed_agent.first_visible_tools is None:
                raise ValueError("missing post-execution G5 rank/tool witness")
            ranks = _private_rank_diagnostic(
                ranked=receipt[0],
                model_visible=observed_agent.first_visible_tools,
                attempted=observed_agent.attempted,
                gold=gold,
                observed_count=row["tool_call_count"],
            )
            if gold is not None:
                if lang in private_rank_by_arm[arm]:
                    raise ValueError("duplicate supported G5 language rank receipt")
                private_rank_by_arm[arm][lang] = ranks
            cells = stats[arm][lang]
            evidence = row["e0_stage_evidence"]
            # Aggregate trusted post-execution E0 stage witnesses only.
            # Do not pass the grading row/labels back to the agent or ranker.
            labels = evidence["observed_stages"]
            if (
                type(labels) is not list
                or any(type(label) is not str for label in labels)
                or evidence.get("visible_candidate_counts") != [5]
                or evidence.get("supported") is not (gold is not None)
                or evidence.get("task_complete") is not row["task_complete"]
                or evidence.get("passed") is not row["passed"]
            ):
                raise ValueError("invalid same-episode E0 funnel witness")
            if gold is not None:
                route_visible = "initial_required_route_not_exposed" not in labels
                completed = bool(row["task_complete"])
                final_after = evidence[
                    "supported_final_after_fixture_completion_observed"
                ]
                if (
                    type(final_after) is not bool
                    or (completed and not route_visible)
                    or (final_after and not completed)
                ):
                    raise ValueError("inconsistent supported G5 E0 stage verdict")
                cells["supported_count"] += 1
                cells["supported_required_route_visible"] += int(route_visible)
                cells["supported_tool_call_attempted"] += int(
                    row["tool_call_count"] > 0
                )
                cells["supported_wrong_operation_observed"] += int(
                    "wrong_operation_attempt_observed" in labels
                )
                cells["supported_schema_rejection_observed"] += int(
                    "input_schema_rejection_observed" in labels
                )
                cells["supported_argument_mismatch_observed"] += int(
                    "task_argument_mismatch_observed" in labels
                )
                cells["supported_fixture_completed"] += int(completed)
                cells["supported_completed_with_final_turn"] += int(final_after)
            else:
                cells["unsupported_count"] += 1
                cells["unsupported_strict_no_call"] += int(row["passed"])
                cells["unsupported_no_call"] += int(
                    row["tool_call_count"] == 0
                )
                cells["unsupported_terminal_mismatch"] += int(
                    "unsupported_no_fit_response_mismatch" in labels
                )
                cells["unsupported_tool_calls"] += int(
                    row["tool_call_count"] > 0
                )
            cells["policy_blocks"] += row["policy_blocks"]
            cells["input_tokens"] += row["input_tokens"]
            cells["schema_tokens"] += row["tool_schema_tokens"]
            cells["candidate_selection_ms"].append(row["candidate_selection_latency_ms"])
            cells["episode_ms"].append(row["episode_wall_latency_ms"])
            for label in evidence["observed_stages"]:
                cells["stage_counts"][label] = cells["stage_counts"].get(label, 0) + 1
    from scripts.evaluate_multilingual_embedding_cpu_dev import percentile

    for langs in stats.values():
        for cell in langs.values():
            for field in ("candidate_selection_ms", "episode_ms"):
                times = cell.pop(field)
                if len(times) != 2:
                    raise ValueError("G5 missing paired agent timing observation")
                cell[f"{field}_p50"] = percentile(times, 50)
                cell[f"{field}_p95"] = percentile(times, 95)

    # Small, source-owned cohort. Absolute counts, NOT calibrated rates,
    # confidence intervals, SLA, final-answer correctness or independent E2.
    funnel: dict[str, dict[str, int | None]] = {}
    for arm in source_arms:
        cells = list(stats[arm].values())
        supported = sum(cell["supported_count"] for cell in cells)
        visible = sum(cell["supported_required_route_visible"] for cell in cells)
        complete = sum(cell["supported_fixture_completed"] for cell in cells)
        final = sum(cell["supported_completed_with_final_turn"] for cell in cells)
        unsupported = sum(cell["unsupported_count"] for cell in cells)
        no_call = sum(cell["unsupported_no_call"] for cell in cells)
        correct_refusal = sum(cell["unsupported_strict_no_call"] for cell in cells)
        terminal_mismatch = sum(
            cell["unsupported_terminal_mismatch"] for cell in cells
        )
        if (
            supported != 3 or unsupported != 3
            or not 0 <= final <= complete <= visible <= supported
            or not 0 <= correct_refusal <= no_call <= unsupported
            or terminal_mismatch > unsupported
        ):
            raise ValueError("invalid G5 E0 retrieval-to-agent funnel")
        funnel[arm] = {
            "supported_cases": supported,
            "supported_required_route_visible": visible,
            "supported_correct_tool_attempts_not_proven": sum(
                cell["supported_tool_call_attempted"] for cell in cells
            ),
            "supported_wrong_operation_observed": sum(
                cell["supported_wrong_operation_observed"] for cell in cells
            ),
            "supported_schema_rejections": sum(
                cell["supported_schema_rejection_observed"] for cell in cells
            ),
            "supported_argument_mismatches": sum(
                cell["supported_argument_mismatch_observed"] for cell in cells
            ),
            "supported_fixture_completed": complete,
            "supported_completed_with_final_turn": final,
            "supported_completed_given_route_visible_denominator": visible,
            "unsupported_cases": unsupported,
            "unsupported_no_call": no_call,
            "unsupported_correct_terminal_refusal": correct_refusal,
            "unsupported_terminal_mismatch": terminal_mismatch,
        }

    return {
        "schema_version": 1,
        "prompt_condition": (
            PROMPT_ARMS[0] if system_prompt == SYSTEM_PROMPT else PROMPT_ARMS[1]
        ),
        "evidence_tier": INJECTED_EVIDENCE,
        "real_qwen_generation_measured": False,
        "real_e5_ranking_measured": False,
        "independent_e2_qualified": False,
        "real_native_provider_execution": False,
        "actual_final_answer_correctness_measured": False,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "case_count": len(cases),
        "supported_cases": 3,
        "unsupported_cases": 3,
        "typed_native_consumer_paths": len(SERVICE_NAMES),
        "fixed_k": 5,
        "source_snapshot_sha256": graph.field_index.snapshot_id,
        "arms": list(source_arms),
        "identical_descriptions_omitted": omit_identical_descriptions,
        "by_arm_language": stats,
        "post_execution_e0_stage_funnel": funnel,
        "post_execution_private_rank_diagnostic": {
            "evidence_tier": "PUBLIC_SYNTHETIC_DEV_POST_EXECUTION_RANK_ONLY",
            "selector_rank_is_model_visible_order": False,
            "model_visible_order": "lexical_sorted_selected_route_names",
            "one_supported_case_per_language": True,
            "tool_or_query_names_exported": False,
            "attempt_arguments_or_generated_text_exported": False,
            "independent_e2_qualified": False,
            "by_arm_language": private_rank_by_arm,
        },
        "limitations": (
            "Actual Qwen generation (if attested) but deterministic "
            "FrozenCorpusExecutor, not genuine external source invocations. "
            "All EN/KO/JA task queries/route gold authored in public DEV; "
            "only one supported step per positive task; no two-hop execution "
            "proof, independent E2, calibrated no-fit, or factual answers. "
            "Task gold supplied only to trusted post-selection fixture grader."
        ),
    }



# Two blocks in reversed order (A, B, B, A), to audit whether the
# previously fixed A→B inference order was responsible for the public
# three-task outcome. Still developer-seen DEV, NOT independent or causal.
BALANCED_PROMPT_ORDER = (
    PROMPT_ARMS[0], PROMPT_ARMS[1], PROMPT_ARMS[1], PROMPT_ARMS[0],
)
FUNNEL_METRICS = (
    "supported_required_route_visible",
    "supported_wrong_operation_observed",
    "supported_fixture_completed",
    "supported_completed_with_final_turn",
    "unsupported_no_call",
    "unsupported_correct_terminal_refusal",
    "unsupported_terminal_mismatch",
)


def summarize_balanced_prompt_runs(
    runs: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Pure fail-closed aggregator; no model, authorization, or E2 scoring."""
    if type(runs) is not tuple or len(runs) != len(BALANCED_PROMPT_ORDER):
        raise ValueError("expected four ABBA unscored fixture reports")
    source: str | None = None
    cells: dict[str, dict[str, list[dict[str, int]]]] = {
        condition: {arm: [] for arm in ARMS}
        for condition in PROMPT_ARMS
    }
    for run, name in zip(runs, BALANCED_PROMPT_ORDER, strict=True):
        if (
            type(run) is not dict
            or run.get("evidence_tier") != INJECTED_EVIDENCE
            or run.get("prompt_condition") != name
            or run.get("arms") != list(ARMS)
            or run.get("case_count") != 6
            or run.get("supported_cases") != 3
            or run.get("unsupported_cases") != 3
            or run.get("fixed_k") != 5
            or run.get("typed_native_consumer_paths") != 24
            or any(run.get(flag) is not False for flag in (
                "independent_e2_qualified", "real_native_provider_execution",
                "actual_final_answer_correctness_measured", "calibrated_no_fit",
                "real_qwen_generation_measured", "real_e5_ranking_measured",
                "product_default_promoted",
            ))
        ):
            raise ValueError("ABBA public DEV run contract or evidence forged")
        current = run.get("source_snapshot_sha256")
        if (
            type(current) is not str or len(current) != 64
            or any(ch not in "0123456789abcdef" for ch in current)
        ):
            raise ValueError("missing immutable native source snapshot witness")
        if source is None:
            source = current
        elif current != source:
            raise ValueError("ABBA source mutation across treatments")
        funnel = run.get("post_execution_e0_stage_funnel")
        if type(funnel) is not dict or set(funnel) != set(ARMS):
            raise ValueError("missing paired source arm in ABBA run")
        for arm in ARMS:
            row = funnel[arm]
            if type(row) is not dict or any(
                type(row.get(key)) is not int
                or not 0 <= row[key] <= 3
                for key in FUNNEL_METRICS
            ):
                raise ValueError("invalid typed ABBA post-execution funnel")
            if (
                row.get("supported_cases") != 3
                or row.get("unsupported_cases") != 3
                or row["supported_completed_with_final_turn"]
                > row["supported_fixture_completed"]
                or row["supported_fixture_completed"]
                > row["supported_required_route_visible"]
                or row["unsupported_correct_terminal_refusal"]
                > row["unsupported_no_call"]
                or row["unsupported_terminal_mismatch"] > 3
            ):
                raise ValueError("contradictory ABBA route or terminal evidence")
            cells[name][arm].append({
                key: row[key] for key in FUNNEL_METRICS
            })
    summary: dict[str, dict[str, Any]] = {}
    for name in PROMPT_ARMS:
        summary[name] = {}
        for arm in ARMS:
            observations = cells[name][arm]
            if len(observations) != 2:
                raise ValueError("prompt must occur in both ABBA positions")
            summary[name][arm] = {
                "supported_denominator": 6,
                "unsupported_denominator": 6,
                "by_position": observations,
                "two_position_pooled_counts": {
                    metric: sum(row[metric] for row in observations)
                    for metric in FUNNEL_METRICS
                },
            }
    return {
        "evidence_tier": "PUBLIC_SYNTHETIC_DEV_ABBA_PROMPT_ORDER_DIAGNOSTIC",
        "sequence": list(BALANCED_PROMPT_ORDER),
        "original_source_snapshot_sha256": source,
        "author_visible_test_cases": True,
        "order_balanced_for_two_blocks": True,
        "randomized": False,
        "independent_e2_qualified": False,
        "calibrated_no_fit": False,
        "real_native_provider_execution": False,
        "scoring_authority": False,
        "model_prompt_tuning_on_public_dev": True,
        "by_prompt_and_source_arm": summary,
        "limitations": (
            "Repeated public synthetic six-case fixtures, fixed ABBA two "
            "blocks only; position drift partly controlled but no new heldout "
            "cases, randomization, independent provider calls, causal effect "
            "or calibrated no-fit. Per-stratum n=3, no production CI/SLA."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-cpu"), required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "real-cpu" and args.out is None:
        raise ValueError("real-model mode requires a report artifact destination")
    if args.mode == "real-cpu":
        from scripts.agent_utility_v7_dev_agent import LocalQwenAgent

        backend, runtime = real_cpu_backend()
        agent = LocalQwenAgent()
        source_revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
            text=True, timeout=10, cwd=ROOT,
        ).stdout.strip()
        # Same original public six task cases in a fixed ABBA order.
        # Every pass constructs fresh current-principal pinned G5 sources,
        # uses the SAME agent, backend, scores and deterministic executor;
        # scorer gold is inaccessible to either model and not exported.
        a1 = run_fixture(backend, agent, source_revision=source_revision)
        b1 = run_fixture(
            backend, agent, source_revision=source_revision,
            system_prompt=GROUNDED_PROMPT,
        )
        b2 = run_fixture(
            backend, agent, source_revision=source_revision,
            system_prompt=GROUNDED_PROMPT,
        )
        a2 = run_fixture(backend, agent, source_revision=source_revision)
        report = a1
        report["prompt_order_balance"] = summarize_balanced_prompt_runs(
            (a1, b1, b2, a2)
        )
        # The original first two legs are retained as a historical
        # diagnostic compatibility view; not independent confirmation.
        report["prompt_comparison"] = {
            "evidence_tier": "PUBLIC_SYNTHETIC_DEV_PROMPT_CONFOUND_DIAGNOSTIC",
            "prompt_conditions": list(PROMPT_ARMS),
            "same_original_synthetic_cases": True,
            "heldout_independent": False,
            "baseline": a1["post_execution_e0_stage_funnel"],
            "inventory_grounded": b1["post_execution_e0_stage_funnel"],
            "inventory_grounded_language": b1["by_arm_language"],
            "limitations": (
                "First AB legs only, sequential public synthetic DEV. "
                "See prompt_order_balance for ABBA positional diagnostics; "
                "neither is a fresh independent heldout nor causal."
            ),
        }
        # Run a separate research-only single-arm grounded-prompt pass,
        # holding the existing agent/tool executor and original six tasks
        # fixed. The only changed candidate text is the repeated ALL-same
        # source-description omitted from E5's authorized option texts.
        # Existing ABBA remains the registered control; no E2 claim.
        short = run_fixture(
            backend, agent, source_revision=source_revision,
            system_prompt=GROUNDED_PROMPT,
            source_arms=("e5_fixed5",),
            omit_identical_descriptions=True,
        )
        if (
            short["arms"] != ["e5_fixed5"]
            or short["identical_descriptions_omitted"] is not True
            or short["source_snapshot_sha256"] != a1["source_snapshot_sha256"]
            or short["case_count"] != 6
            or short["fixed_k"] != 5
            or short["independent_e2_qualified"] is not False
            or short["real_native_provider_execution"] is not False
            or short["calibrated_no_fit"] is not False
        ):
            raise ValueError("source/authority drift in G5 agent description ablation")
        report["common_description_agent_ablation"] = {
            "evidence_tier": "REAL_PINNED_QWEN_E5_COMMON_SOURCE_DEV_NOT_E2",
            "condition": "grounded_prompt_e5_fixed5_omit_all_identical_source_description",
            "original_synthetic_cases_unchanged": True,
            "source_snapshot_sha256": a1["source_snapshot_sha256"],
            "same_original_scoring_and_authorized_executor": True,
            "reference_legacy_grounded": b1[
                "post_execution_e0_stage_funnel"
            ]["e5_fixed5"],
            "reference_reverse_grounded": b2[
                "post_execution_e0_stage_funnel"
            ]["e5_fixed5"],
            "shortened_ranker_observation": short[
                "post_execution_e0_stage_funnel"
            ]["e5_fixed5"],
            "shortened_ranker_by_language": short[
                "by_arm_language"
            ]["e5_fixed5"],
            "reference_grounded_positions_by_language": b1[
                "post_execution_private_rank_diagnostic"
            ]["by_arm_language"]["e5_fixed5"],
            "reference_reverse_positions_by_language": b2[
                "post_execution_private_rank_diagnostic"
            ]["by_arm_language"]["e5_fixed5"],
            "shortened_positions_by_language": short[
                "post_execution_private_rank_diagnostic"
            ]["by_arm_language"]["e5_fixed5"],
            "selector_ranking_not_forwarded_to_agent": True,
            "independent_heldout": False,
            "final_answer_factual_oracle_measured": False,
            "calibrated_no_fit": False,
            "real_external_provider_execution": False,
            "default_policy_changed": False,
            "limitations": (
                "One additional 6-case synthetic DEV after the ABBA runs; "
                "nonrandomized run order, agent warmup/time drift, original "
                "seen source/task gold, no actual original provider execution "
                "or end-to-end independent E2."
            ),
        }
        # The attestation is only made here, after actual pinned E5+Qwen
        # objects were constructed and the complete fixture run succeeded.
        if runtime["model_id"] != E5_MODEL_ID or (
            runtime["model_revision"] != E5_MODEL_REVISION
        ):
            raise ValueError("unverified E5 runtime revision")
        report["evidence_tier"] = FIXTURE_EVIDENCE
        report["real_qwen_generation_measured"] = True
        report["real_e5_ranking_measured"] = True
        report["runtime"] = {
            "agent_model": AGENT_MODEL_ID,
            "agent_revision": AGENT_MODEL_REVISION,
            "e5_model": E5_MODEL_ID,
            "e5_revision": E5_MODEL_REVISION,
            "device": runtime["device"],
            "python": platform.python_version(),
        }
    else:
        class RefusingAgent:
            def generate(self, _messages, tools):
                return {
                    "text": "REQUEST_MORE_TOOLS",
                    "input_tokens": 10, "tool_tokens": 2 * len(tools),
                    "output_tokens": 3, "latency_ms": 0.0,
                    "context_overflow": False,
                }

        report = run_fixture(
            CallableDecisionBackend(_first_five), RefusingAgent(),
            source_revision="0" * 40,
        )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
