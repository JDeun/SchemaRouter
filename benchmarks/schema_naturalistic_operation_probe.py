# ruff: noqa: E501
"""Naturalistic generic-operation linear-probe membership for experiment #404.

Frozen BGE-M3 remains the sole positive route selector. A separately frozen
MiniLM representation plus registry-independent linear probes may only preserve
that raw registered winner or veto to NO_ROUTE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks.schema_adb_baseline import (
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
    compile_registry_contracts,
)

MINILM_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MINILM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"

PROBE_C = 1.0
PROBE_SOLVER = "lbfgs"
PROBE_MAX_ITER = 3000
PROBE_RANDOM_STATE = 20260929

TOOL_OPERATION = "TOOL_OPERATION"
BACKGROUND = "BACKGROUND"

BANK_PATH = Path(__file__).with_name("v6f-naturalistic-utterance-bank.json")


@dataclass(frozen=True)
class NaturalisticBank:
    languages: tuple[str, ...]
    operation_labels: tuple[str, ...]
    operation_texts: tuple[str, ...]
    operation_targets: tuple[str, ...]
    background_texts: tuple[str, ...]


@dataclass
class ProbeModels:
    scope: Any
    operation: Any
    width: int


def load_naturalistic_bank(path: Path = BANK_PATH) -> NaturalisticBank:
    data = json.loads(path.read_text(encoding="utf-8"))
    languages = tuple(str(value) for value in data["languages"])
    operation_labels = tuple(str(value) for value in data["operation_labels"])

    operation_texts: list[str] = []
    operation_targets: list[str] = []
    operation_rows = data["operation_utterances"]
    for label in operation_labels:
        by_language = operation_rows[label]
        for language in languages:
            for text in by_language[language]:
                operation_texts.append(str(text))
                operation_targets.append(label)

    background_texts: list[str] = []
    for family in data["background_families"]:
        by_language = data["background_utterances"][family]
        for language in languages:
            background_texts.extend(str(text) for text in by_language[language])

    if len(operation_texts) != 432:
        raise ValueError("V6F operation bank must contain exactly 432 utterances")
    if len(background_texts) != 384:
        raise ValueError("V6F background bank must contain exactly 384 utterances")
    all_texts = [*operation_texts, *background_texts]
    if len(all_texts) != len(set(all_texts)):
        raise ValueError("V6F naturalistic bank utterances must be globally unique")

    return NaturalisticBank(
        languages=languages,
        operation_labels=operation_labels,
        operation_texts=tuple(operation_texts),
        operation_targets=tuple(operation_targets),
        background_texts=tuple(background_texts),
    )


def fit_probe_models(
    semantic_embedder: Any,
    *,
    bank: NaturalisticBank | None = None,
) -> ProbeModels:
    from sklearn.linear_model import LogisticRegression

    bank = bank or load_naturalistic_bank()
    all_texts = [*bank.operation_texts, *bank.background_texts]
    vectors = _to_vectors(semantic_embedder(all_texts))
    if len(vectors) != len(all_texts):
        raise ValueError("semantic evidence embedding count mismatch")
    if not vectors or not vectors[0]:
        raise ValueError("semantic evidence embeddings are empty")

    operation_count = len(bank.operation_texts)
    operation_vectors = vectors[:operation_count]

    scope_targets = [
        *([TOOL_OPERATION] * operation_count),
        *([BACKGROUND] * len(bank.background_texts)),
    ]

    scope = LogisticRegression(
        penalty="l2",
        C=PROBE_C,
        solver=PROBE_SOLVER,
        max_iter=PROBE_MAX_ITER,
        random_state=PROBE_RANDOM_STATE,
        class_weight=None,
    )
    scope.fit(vectors, scope_targets)

    operation = LogisticRegression(
        penalty="l2",
        C=PROBE_C,
        solver=PROBE_SOLVER,
        max_iter=PROBE_MAX_ITER,
        random_state=PROBE_RANDOM_STATE,
        class_weight=None,
    )
    operation.fit(operation_vectors, list(bank.operation_targets))

    return ProbeModels(
        scope=scope,
        operation=operation,
        width=len(vectors[0]),
    )


def apply_membership_decision(
    *,
    raw_top_route: str,
    scope_class: str,
    operation_class: str | None,
    supported_leaves: set[str],
    unknown_tool: bool,
) -> tuple[str | None, str]:
    """Apply the preregistered negative-only V6F decision rule."""
    if unknown_tool:
        return raw_top_route, "unknown_operation_semantics_preserve"
    if scope_class == BACKGROUND:
        return None, "background_probe_veto"
    if scope_class != TOOL_OPERATION:
        raise ValueError(f"unexpected scope class: {scope_class}")
    if operation_class is None:
        raise ValueError("operation class is required for tool-operation scope")
    if operation_class not in supported_leaves:
        return None, "unsupported_operation_probe_veto"
    return raw_top_route, "registered_operation_probe_preserve"


class SchemaNaturalisticProbeRouter:
    """Frozen BGE routing plus naturalistic MiniLM linear-probe veto."""

    def __init__(
        self,
        registry: Any,
        bge_embedder: Any,
        semantic_embedder: Any,
    ) -> None:
        self.registry = registry
        self.bge_embedder = bge_embedder
        self.semantic_embedder = semantic_embedder
        self.contracts = compile_registry_contracts(registry)
        self.probes = fit_probe_models(semantic_embedder)

        route_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )

        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_count = len(self.route_ids)
        route_vectors = _to_vectors(
            bge_embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                ]
            )
        )
        if len(route_vectors) != route_count * 2:
            raise ValueError("unexpected route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, route_vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, route_vectors[route_count:], strict=True)
        )

        contracts_by_tool: dict[str, list[Any]] = {}
        for contract in self.contracts.values():
            contracts_by_tool.setdefault(contract.tool_key, []).append(contract)

        self.unknown_tools: set[str] = set()
        self.supported_leaves: dict[str, frozenset[str]] = {}
        for tool_key, contracts in contracts_by_tool.items():
            if any(contract.leaf is None for contract in contracts):
                self.unknown_tools.add(tool_key)
                continue
            self.supported_leaves[tool_key] = frozenset(
                str(contract.leaf) for contract in contracts
            )

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT * _cosine(query_vector, self.action_vectors[route_id])
            )
            rows.append((route_id, score))
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows

    def route(self, query: str) -> dict[str, Any]:
        bge_vector = _to_vectors(self.bge_embedder([query]))[0]
        raw_ranked = self._rank_raw(bge_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        if raw_tool in self.unknown_tools or raw_tool not in self.supported_leaves:
            predicted, reason = apply_membership_decision(
                raw_top_route=raw_top_route,
                scope_class=TOOL_OPERATION,
                operation_class=None,
                supported_leaves=set(),
                unknown_tool=True,
            )
            scope_class = None
            operation_class = None
        else:
            semantic_vector = _to_vectors(self.semantic_embedder([query]))[0]
            if len(semantic_vector) != self.probes.width:
                raise ValueError("semantic query embedding width mismatch")
            scope_class = str(self.probes.scope.predict([semantic_vector])[0])
            operation_class = None
            if scope_class == TOOL_OPERATION:
                operation_class = str(
                    self.probes.operation.predict([semantic_vector])[0]
                )
            predicted, reason = apply_membership_decision(
                raw_top_route=raw_top_route,
                scope_class=scope_class,
                operation_class=operation_class,
                supported_leaves=set(self.supported_leaves[raw_tool]),
                unknown_tool=False,
            )

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_operation_semantics": raw_tool in self.unknown_tools,
            "scope_class": scope_class,
            "operation_class": operation_class,
            "supported_leaves": sorted(self.supported_leaves.get(raw_tool, ())),
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
