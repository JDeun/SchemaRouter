# ruff: noqa: E501
"""External multilingual zero-shot capability-set membership veto for experiment #371.

The frozen BGE-M3 route is the sole positive selector. The external zero-shot classifier can only
preserve that registered winner or veto to NO_ROUTE.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

BGE_MODEL = "BAAI/bge-m3"
BGE_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
ZERO_SHOT_MODEL = "Horizon-Labs/multilingual-zeroshot-small"
ZERO_SHOT_REVISION = "v1.1"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45
HYPOTHESIS_TEMPLATE = "The user wants to {}."
OUTSIDE_LABEL = "request an operation outside the registered capabilities of this tool"

LEAF_ORDER = (
    "search",
    "retrieve",
    "list",
    "create",
    "update",
    "delete",
    "cancel",
    "refund",
    "send",
    "share",
    "export",
    "translate",
    "summarize",
    "compare",
    "merge",
    "restart",
    "execute",
    "forecast",
)

LEAF_LABELS: dict[str, str] = {
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

CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "search": ("search", "find", "query", "검색", "찾기", "buscar", "検索", "suchen"),
    "retrieve": ("retrieve", "get one", "lookup", "details", "조회", "불러", "obtener", "取得", "abrufen"),
    "list": ("list", "enumerate", "all ", "목록", "listar", "一覧", "auflisten"),
    "create": ("create", "register", "add new", "schedule", "생성", "등록", "crear", "作成", "erstellen"),
    "update": ("update", "edit", "change", "modify", "수정", "변경", "actualizar", "更新", "ändern"),
    "delete": ("delete", "remove", "erase", "purge", "삭제", "제거", "eliminar", "削除", "löschen"),
    "cancel": ("cancel", "revoke", "abort", "취소", "철회", "cancelar", "キャンセル", "stornieren"),
    "refund": ("refund", "reimburse", "환불", "reembolso", "返金", "erstatten"),
    "send": ("send", "dispatch", "deliver", "forward", "전송", "보내", "enviar", "送信", "senden"),
    "share": ("share", "grant access", "공유", "compartir", "共有", "teilen"),
    "export": ("export", "download", "내보내", "다운로드", "exportar", "エクスポート", "exportieren"),
    "translate": ("translate", "번역", "traducir", "翻訳", "übersetzen"),
    "summarize": ("summarize", "summary", "요약", "resumir", "要約", "zusammenfassen"),
    "compare": ("compare", "contrast", "비교", "comparar", "比較", "vergleichen"),
    "merge": ("merge", "combine", "consolidate", "병합", "fusionar", "統合", "zusammenführen"),
    "restart": ("restart", "reboot", "재시작", "reiniciar", "再起動", "neustarten"),
    "execute": ("execute", "run workflow", "trigger", "invoke", "실행", "ejecutar", "実行", "ausführen"),
    "forecast": ("forecast", "predict", "future", "예측", "pronóstico", "予測", "prognose"),
}

METHOD_LEAF = {
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    leaf: str | None
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]


def _normalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _contains(text: str, phrase: str) -> bool:
    haystack = _normalize(text)
    needle = _normalize(phrase)
    if not needle:
        return False
    if any(ord(char) > 127 for char in needle) or " " in needle:
        return needle in haystack
    return f" {needle} " in f" {haystack} "


def _endpoint_text(endpoint: Any) -> str:
    return "\n".join(
        str(value)
        for value in [
            endpoint.name,
            *endpoint.operation_aliases,
            endpoint.description,
            endpoint.path or "",
        ]
        if str(value).strip()
    )


def infer_endpoint_leaf(endpoint: Any) -> str | None:
    method = str(endpoint.method).upper() if endpoint.method else None
    if endpoint.destructive is True or method == "DELETE":
        return "delete"
    if method in METHOD_LEAF:
        return METHOD_LEAF[method]

    text = _endpoint_text(endpoint)
    for leaf, hints in CONTRACT_HINTS.items():
        if any(_contains(text, hint) for hint in hints):
            return leaf
    return None


def _schema_type(schema: dict[str, Any]) -> str:
    raw = schema.get("type")
    if isinstance(raw, str):
        base = raw
    elif isinstance(raw, list):
        base = "|".join(str(value) for value in raw)
    elif isinstance(schema.get("properties"), dict):
        base = "object"
    else:
        base = "unknown"
    if base == "array" and isinstance(schema.get("items"), dict):
        return f"array<{_schema_type(schema['items'])}>"
    return base


def _data_contract(endpoint: Any) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for parameter in endpoint.parameters:
        rows.append(
            {
                "role": "input",
                "name": str(parameter.name),
                "type": _schema_type(parameter.json_schema),
                "required": bool(parameter.required),
            }
        )
    for field in endpoint.output_fields:
        normalization = field.unit_normalization
        rows.append(
            {
                "role": "output",
                "name": str(field.name),
                "semantic_id": field.semantic_id,
                "type": _schema_type(field.json_schema),
                "source_unit": field.unit,
                "canonical_unit": (
                    normalization.canonical_unit
                    if normalization is not None
                    else None
                ),
                "dimension": (
                    normalization.dimension
                    if normalization is not None
                    else None
                ),
                "scale": normalization.scale if normalization is not None else None,
                "offset": normalization.offset if normalization is not None else None,
                "qualifiers": dict(field.qualifiers),
                "identifier": bool(field.identifier),
            }
        )
    return tuple(rows)


def compile_registry_contracts(registry: Any) -> dict[str, RouteContract]:
    contracts: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            contracts[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                leaf=infer_endpoint_leaf(endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return contracts


def capability_labels(supported_leaves: set[str]) -> list[str]:
    labels = [
        LEAF_LABELS[leaf]
        for leaf in LEAF_ORDER
        if leaf in supported_leaves
    ]
    labels.append(OUTSIDE_LABEL)
    return labels


def decide_membership(
    *,
    top_label: str,
    supported_leaves: set[str],
    tool_has_unknown: bool,
) -> tuple[bool, str]:
    """Return (veto, reason) for the exact preregistered membership rule."""
    if tool_has_unknown:
        return False, "unknown_endpoint_semantics_preserve"
    allowed = set(capability_labels(supported_leaves))
    if top_label not in allowed:
        raise ValueError(f"zero-shot classifier returned unknown label: {top_label}")
    if top_label == OUTSIDE_LABEL:
        return True, "outside_label_top1"
    return False, "supported_label_top1"


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must align")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vectors must have non-zero norm")
    return max(
        -1.0,
        min(
            1.0,
            sum(a * b for a, b in zip(left, right, strict=True))
            / (left_norm * right_norm),
        ),
    )


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [[float(value) for value in vector] for vector in raw]
    if not vectors or any(not vector for vector in vectors):
        raise ValueError("embedder returned empty vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("embedder returned non-finite values")
    return vectors


def _schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [route_id, tool.description.strip(), endpoint.description.strip()]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    aliases = list(endpoint.operation_aliases)
    fallback = endpoint.description.strip() if not aliases else ""
    return "\n".join(
        dict.fromkeys(part for part in [operation_name, *aliases, fallback] if part)
    )


class ExternalZeroShotMembershipRouter:
    """Preserve raw BGE route unless the external classifier selects OUTSIDE."""

    def __init__(
        self,
        registry: Any,
        bge_embedder: Any,
        zero_shot_classifier: Any,
    ) -> None:
        self.registry = registry
        self.bge_embedder = bge_embedder
        self.zero_shot_classifier = zero_shot_classifier
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

        static = _to_vectors(
            bge_embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                ]
            )
        )
        route_count = len(self.route_ids)
        if len(static) != route_count * 2:
            raise ValueError("unexpected BGE static embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, static[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(
                self.route_ids,
                static[route_count:],
                strict=True,
            )
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
        query_vector = _to_vectors(self.bge_embedder([query]))[0]
        raw_ranked = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_contracts = [
            contract
            for contract in self.contracts.values()
            if contract.tool_key == raw_tool
        ]
        supported_leaves = {
            contract.leaf
            for contract in tool_contracts
            if contract.leaf is not None
        }
        tool_has_unknown = any(
            contract.leaf is None
            for contract in tool_contracts
        )

        if tool_has_unknown:
            top_label = None
            scores = None
            veto = False
            veto_reason = "unknown_endpoint_semantics_preserve"
            labels = capability_labels(supported_leaves)
        else:
            labels = capability_labels(supported_leaves)
            result = self.zero_shot_classifier(
                query,
                labels,
                HYPOTHESIS_TEMPLATE,
            )
            top_label = str(result["top_label"])
            raw_scores = result.get("scores")
            scores = (
                {str(key): float(value) for key, value in raw_scores.items()}
                if isinstance(raw_scores, dict)
                else None
            )
            veto, veto_reason = decide_membership(
                top_label=top_label,
                supported_leaves=supported_leaves,
                tool_has_unknown=False,
            )

        predicted = None if veto else raw_top_route
        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_supported_leaves": sorted(supported_leaves),
            "tool_has_unknown_leaf": tool_has_unknown,
            "candidate_labels": labels,
            "zero_shot_top_label": top_label,
            "zero_shot_scores": scores,
            "veto": veto,
            "veto_reason": veto_reason,
            "raw_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in raw_ranked
            ],
        }
