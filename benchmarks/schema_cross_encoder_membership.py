# ruff: noqa: E501
"""Relative multilingual cross-encoder capability membership for V6G / #408.

Frozen BGE-M3 remains the sole positive route selector. The cross-encoder sees
registered supported capability documents, same-resource counterfactual
capabilities, and a fixed generic background bank. It may only preserve the
raw BGE winner or veto to NO_ROUTE.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
from benchmarks.schema_knn_membership import BACKGROUND_ANCHORS

RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RERANKER_REVISION = "2a0ed9295b28874866ea121f341ed150267f86a3"
RERANKER_MAX_LENGTH = 192

LEAF_DESCRIPTIONS = {
    "search": "search for unknown matching existing items by criteria",
    "retrieve": "retrieve one already identified existing item",
    "list": "list a collection of existing items",
    "create": "create a brand-new resource",
    "update": "update fields or settings of an existing resource",
    "delete": "permanently delete an existing resource",
    "cancel": "cancel or stop an active request or process",
    "refund": "refund money for a payment or completed transaction",
    "send": "send or deliver an item or message to a destination",
    "share": "share access to an existing resource with another user",
    "export": "export or download existing data as an external file",
    "translate": "translate content into another human language",
    "summarize": "summarize content into its main points",
    "compare": "compare multiple items for similarities or differences",
    "merge": "merge multiple resources into one result",
    "restart": "restart or reboot an existing machine service or job",
    "execute": "execute or launch a registered workflow or operation",
    "forecast": "forecast a future value state trend or outcome",
}

PairScorer = Callable[[str, list[str]], list[float]]


@dataclass(frozen=True)
class CapabilityDocument:
    evidence_id: str
    kind: str
    leaf: str | None
    text: str


@dataclass(frozen=True)
class ToolEvidenceBank:
    tool_key: str
    supported: tuple[CapabilityDocument, ...]
    complement: tuple[CapabilityDocument, ...]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _field_fact(row: dict[str, Any]) -> str:
    parts = [
        f"role={_clean(row.get('role'))}",
        f"name={_clean(row.get('name'))}",
        f"type={_clean(row.get('type'))}",
    ]
    for key in ("semantic_id", "source_unit", "canonical_unit", "dimension"):
        value = row.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={_clean(value)}")
    qualifiers = row.get("qualifiers")
    if isinstance(qualifiers, dict) and qualifiers:
        parts.append(
            "qualifiers="
            + ",".join(
                f"{_clean(key)}={_clean(value)}"
                for key, value in sorted(qualifiers.items())
            )
        )
    return "; ".join(parts)


def _supported_document(
    *,
    tool: Any,
    endpoint: Any,
    contract: Any,
) -> CapabilityDocument:
    access = "; ".join(
        [
            f"method={contract.method or 'unknown'}",
            (
                "read_only="
                + (
                    str(contract.read_only).lower()
                    if contract.read_only is not None
                    else "unknown"
                )
            ),
            (
                "destructive="
                + (
                    str(contract.destructive).lower()
                    if contract.destructive is not None
                    else "unknown"
                )
            ),
        ]
    )
    data = " | ".join(
        sorted(_field_fact(row) for row in contract.data_contract)
    )
    lines = [
        "registered capability",
        f"tool: {_clean(tool.key)}",
        f"tool scope: {_clean(tool.description)}",
        f"operation: {LEAF_DESCRIPTIONS[contract.leaf]}",
        f"resource: {_clean(contract.resource_anchor)}",
        f"endpoint capability: {_clean(endpoint.description)}",
        f"access: {access}",
    ]
    if data:
        lines.append(f"data: {data}")
    return CapabilityDocument(
        evidence_id=contract.route_id,
        kind="supported",
        leaf=contract.leaf,
        text="\n".join(lines),
    )


def _counterfactual_document(
    *,
    tool_key: str,
    resource_anchor: str,
    leaf: str,
) -> CapabilityDocument:
    return CapabilityDocument(
        evidence_id=f"{tool_key}::counterfactual::{resource_anchor}::{leaf}",
        kind="complement",
        leaf=leaf,
        text="\n".join(
            [
                "counterfactual capability",
                f"operation: {LEAF_DESCRIPTIONS[leaf]}",
                f"resource: {_clean(resource_anchor)}",
            ]
        ),
    )


def compile_tool_evidence_banks(
    registry: Any,
) -> tuple[dict[str, ToolEvidenceBank], set[str]]:
    contracts = compile_registry_contracts(registry)
    tools = {str(tool.key): tool for tool in registry.tools()}
    endpoints: dict[str, Any] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            endpoints[f"{tool.key}.{endpoint.name}"] = endpoint

    by_tool: dict[str, list[Any]] = {}
    for contract in contracts.values():
        by_tool.setdefault(contract.tool_key, []).append(contract)

    banks: dict[str, ToolEvidenceBank] = {}
    unknown_tools: set[str] = set()

    for tool_key, tool_contracts in sorted(by_tool.items()):
        if any(contract.leaf not in LEAF_DESCRIPTIONS for contract in tool_contracts):
            unknown_tools.add(tool_key)
            continue

        supported_docs = tuple(
            _supported_document(
                tool=tools[tool_key],
                endpoint=endpoints[contract.route_id],
                contract=contract,
            )
            for contract in sorted(tool_contracts, key=lambda item: item.route_id)
        )
        supported_leaves = {str(contract.leaf) for contract in tool_contracts}
        complement_leaves = [
            leaf for leaf in LEAF_DESCRIPTIONS if leaf not in supported_leaves
        ]
        resource_anchors = sorted(
            {
                _clean(contract.resource_anchor)
                for contract in tool_contracts
                if _clean(contract.resource_anchor)
            }
        )
        if not resource_anchors or not complement_leaves:
            unknown_tools.add(tool_key)
            continue

        complement_docs = tuple(
            _counterfactual_document(
                tool_key=tool_key,
                resource_anchor=resource_anchor,
                leaf=leaf,
            )
            for resource_anchor in resource_anchors
            for leaf in complement_leaves
        )
        banks[tool_key] = ToolEvidenceBank(
            tool_key=tool_key,
            supported=supported_docs,
            complement=complement_docs,
        )

    return banks, unknown_tools


BACKGROUND_DOCUMENTS = tuple(
    CapabilityDocument(
        evidence_id=f"background::{index:02d}",
        kind="background",
        leaf=None,
        text=anchor,
    )
    for index, anchor in enumerate(BACKGROUND_ANCHORS, start=1)
)


class RelativeCrossEncoderCapabilityGate:
    """BGE positive routing plus threshold-free relative cross-encoder veto."""

    def __init__(
        self,
        registry: Any,
        *,
        bge_embedder: Callable[[list[str]], list[list[float]]],
        pair_scorer: PairScorer,
    ) -> None:
        self.registry = registry
        self.bge_embedder = bge_embedder
        self.pair_scorer = pair_scorer
        self.contracts = compile_registry_contracts(registry)

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
        count = len(self.route_ids)
        vectors = _to_vectors(
            bge_embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                ]
            )
        )
        if len(vectors) != count * 2:
            raise ValueError("unexpected BGE route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, vectors[:count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, vectors[count:], strict=True)
        )

        self.banks, self.unknown_tools = compile_tool_evidence_banks(registry)

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        ranking = [
            (
                route_id,
                SCHEMA_WEIGHT * _cosine(
                    query_vector, self.schema_vectors[route_id]
                )
                + ACTION_WEIGHT * _cosine(
                    query_vector, self.action_vectors[route_id]
                ),
            )
            for route_id in self.route_ids
        ]
        ranking.sort(key=lambda item: (-item[1], item[0]))
        return ranking

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.bge_embedder([query]))[0]
        raw_ranking = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranking[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        if raw_tool in self.unknown_tools or raw_tool not in self.banks:
            return {
                "predicted": raw_top_route,
                "raw_top_route": raw_top_route,
                "raw_top_score": raw_top_score,
                "raw_tool": raw_tool,
                "supported_max": None,
                "complement_max": None,
                "background_max": None,
                "negative_max": None,
                "negative_advantage": None,
                "best_supported": None,
                "best_complement": None,
                "negative_source": None,
                "reason": "unknown_tool_evidence_preserve",
                "raw_ranked_routes": [
                    {"route_id": route_id, "score": score}
                    for route_id, score in raw_ranking
                ],
            }

        bank = self.banks[raw_tool]
        documents = [*bank.supported, *bank.complement, *BACKGROUND_DOCUMENTS]
        scores = [float(value) for value in self.pair_scorer(
            str(query), [document.text for document in documents]
        )]
        if len(scores) != len(documents):
            raise ValueError("cross-encoder score count mismatch")

        scored = list(zip(documents, scores, strict=True))
        supported_rows = [
            (doc, score) for doc, score in scored if doc.kind == "supported"
        ]
        complement_rows = [
            (doc, score) for doc, score in scored if doc.kind == "complement"
        ]
        background_rows = [
            (doc, score) for doc, score in scored if doc.kind == "background"
        ]
        if not supported_rows or not complement_rows or not background_rows:
            raise ValueError("V6G evidence partitions must be non-empty")

        best_supported, supported_max = max(
            supported_rows, key=lambda item: (item[1], item[0].evidence_id)
        )
        best_complement, complement_max = max(
            complement_rows, key=lambda item: (item[1], item[0].evidence_id)
        )
        best_background, background_max = max(
            background_rows, key=lambda item: (item[1], item[0].evidence_id)
        )

        if complement_max >= background_max:
            negative_max = complement_max
            negative_source = "complement"
            best_negative = best_complement
        else:
            negative_max = background_max
            negative_source = "background"
            best_negative = best_background

        if negative_max > supported_max:
            predicted = None
            reason = f"{negative_source}_cross_encoder_closer"
        else:
            predicted = raw_top_route
            reason = "registered_cross_encoder_not_outscored"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "supported_max": supported_max,
            "complement_max": complement_max,
            "background_max": background_max,
            "negative_max": negative_max,
            "negative_advantage": negative_max - supported_max,
            "best_supported": {
                "evidence_id": best_supported.evidence_id,
                "leaf": best_supported.leaf,
                "score": supported_max,
            },
            "best_complement": {
                "evidence_id": best_complement.evidence_id,
                "leaf": best_complement.leaf,
                "score": complement_max,
            },
            "best_negative": {
                "evidence_id": best_negative.evidence_id,
                "leaf": best_negative.leaf,
                "score": negative_max,
            },
            "negative_source": negative_source,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranking
            ],
        }
