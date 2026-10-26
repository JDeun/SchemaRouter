"""Opt-in A7 native baseline-vs-paper agent pairing; synthetic E0 only.

Reuses the one original principal-scoped fixed5 executor and the existing A7
paper meter. Frozen DEV fixtures and author claims are never independent E2.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from schemarouter import InMemoryRegistry, PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    GeneratedEpisodeAgent,
    run_generated_episode,
    sha256_json,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_measured_episode_e0 import (
    PaperMeteredAgentEpisode,
    PaperMeteredModel,
    run_paper_measured_agent_episode_e0,
)
from scripts.research_paper_scoped_understand_e0 import _validated_owner_snapshot


@dataclass(frozen=True)
class HostAgentPairConfiguration:
    """Unverified host assertion of equivalent model/agent/seed settings."""

    agent_revision: str
    model_revision: str
    seed: int
    sampling_parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PaperPairedAgentE0:
    """Source-scoped sanitized metrics only; never an independent E2 score."""

    baseline: dict[str, Any]
    baseline_tool_schema_utf8_bytes_exposed: int
    paper: PaperMeteredAgentEpisode
    host_declared_matching_agent_configuration: bool = True
    independent_e2_qualified: bool = False


PaperAgentFactory = Callable[
    [], tuple[GeneratedEpisodeAgent, HostAgentPairConfiguration],
]


def _validated_config(value: Any) -> HostAgentPairConfiguration:
    if type(value) is not HostAgentPairConfiguration:
        raise ValueError("matching fresh agent configuration required")
    if (
        type(value.agent_revision) is not str
        or not 1 <= len(value.agent_revision.strip()) <= 128
        or type(value.model_revision) is not str
        or not 1 <= len(value.model_revision.strip()) <= 128
        or type(value.seed) is not int
        or not 0 <= value.seed <= 2**32 - 1
        or type(value.sampling_parameters) is not tuple
        or not 1 <= len(value.sampling_parameters) <= 16
    ):
        raise ValueError("matching fresh agent configuration required")
    if any(
        type(item) is not tuple or len(item) != 2
        or type(item[0]) is not str or type(item[1]) is not str
        or re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,63}", item[0]) is None
        or not 1 <= len(item[1].strip()) <= 128
        for item in value.sampling_parameters
    ) or tuple(sorted(value.sampling_parameters)) != value.sampling_parameters or len({
        item[0] for item in value.sampling_parameters
    }) != len(value.sampling_parameters):
        raise ValueError("matching fresh agent configuration required")
    return value


async def run_paper_paired_agent_e0(
    model: PaperMeteredModel,
    agent_factory: PaperAgentFactory,
    *,
    view: AuthorizedAgentToolSurface,
    task: dict[str, Any],
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
) -> PaperPairedAgentE0:
    """Compare captured authorized ranked K5 with paper K5 on the same case.

    The existing fixed5 loop owns *both* executions, and A5 owns the paper
    source proof. The factory is called twice for fresh same-config agents;
    its revision claim cannot independently authenticate the external model.
    A failure in either branch discards the whole comparison.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("original principal-scoped view required")
    if not isinstance(view.router.registry, InMemoryRegistry):
        raise ValueError("paired E0 requires the original in-memory agent registry")
    if type(task) is not dict or task.get("query") != view.original_query:
        raise ValueError("paired task/query mismatch")
    if not callable(model) or not callable(agent_factory):
        raise ValueError("paired model and agent factory must be callable")
    view.assert_source_unchanged()
    owner_before = _validated_owner_snapshot(intent_registry, catalog)

    def assert_owner_unchanged() -> None:
        view.assert_source_unchanged()
        if _validated_owner_snapshot(intent_registry, catalog) != owner_before:
            raise PolicyViolationError("paired owner declarations changed")

    try:
        # The legacy benchmark digest intentionally mirrors its old frozen
        # input encoding, which may serialize NaN. Refuse such task evidence
        # before either condition so no invalid gold can enter a pair.
        json.dumps(task, allow_nan=False)
        frozen_task = copy.deepcopy(task)
        original_digest = sha256_json(task)
        if sha256_json(frozen_task) != original_digest:
            raise ValueError("paired source task cannot be frozen")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError("paired source task cannot be frozen") from None

    def assert_original_task() -> None:
        try:
            if sha256_json(task) != original_digest:
                raise ValueError("paired source task evidence changed")
        except (TypeError, OverflowError, RecursionError):
            raise ValueError("paired source task evidence changed") from None

    first = agent_factory()
    second = agent_factory()
    if (
        type(first) is not tuple or len(first) != 2
        or type(second) is not tuple or len(second) != 2
    ):
        raise ValueError("matching fresh agent configuration required")
    baseline_agent, baseline_config = first
    paper_agent, paper_config = second
    if (
        baseline_agent is paper_agent
        or type(baseline_agent) is not type(paper_agent)
        or _validated_config(baseline_config) != _validated_config(paper_config)
        or not callable(getattr(baseline_agent, "generate", None))
        or not callable(getattr(paper_agent, "generate", None))
    ):
        raise ValueError("matching fresh agent configuration required")
    assert_original_task()
    assert_owner_unchanged()

    def select_original_ranked_k5(query: str, source_ids: tuple[str, ...]) -> list[str]:
        view.assert_source_unchanged()
        assert_original_task()
        if query != view.original_query or source_ids != view.visible_route_ids:
            raise PolicyViolationError("paired baseline source identities changed")
        return list(source_ids[:5])

    baseline_schema_bytes = 0

    class BaselineSchemaMeter:
        def generate(
            self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
        ) -> dict[str, Any]:
            nonlocal baseline_schema_bytes
            baseline_schema_bytes += len(json.dumps(
                tools, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8"))
            return baseline_agent.generate(messages, tools)

    baseline = run_generated_episode(
        BaselineSchemaMeter(), view.router.registry, copy.deepcopy(frozen_task),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=select_original_ranked_k5,
        experimental_agent_tool_surface=view,
        experimental_host_empty_menu_terminal=True,
    )
    assert_original_task()
    assert_owner_unchanged()
    paper = await run_paper_measured_agent_episode_e0(
        model, paper_agent, view=view, task=copy.deepcopy(frozen_task),
        catalog=catalog, intent_registry=intent_registry, index=index,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    assert_original_task()
    assert_owner_unchanged()
    # The original A5 public trace legitimately includes the private grader's
    # `supported` stratum boolean. Paired E0 exports task outcome metrics,
    # never the per-case ground-truth disposition used for future holdouts.
    return PaperPairedAgentE0(
        baseline={key: value for key, value in baseline.items() if key != "supported"},
        baseline_tool_schema_utf8_bytes_exposed=baseline_schema_bytes,
        paper=replace(
            paper, episode={
                key: value for key, value in paper.episode.items()
                if key != "supported"
            },
        ),
    )
