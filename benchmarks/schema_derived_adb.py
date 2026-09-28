# ruff: noqa: E501
"""Schema-derived adaptive decision-boundary baseline for experiment #384.

Research-only. Frozen BGE-M3 remains the sole positive endpoint selector.
Endpoint boundaries are compiled at registry/index-build time from trusted schema metadata only.
The ADB layer can preserve the raw registered route or veto to NO_ROUTE; it never selects another
endpoint and never invents execution authority.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

BGE_MODEL = "BAAI/bge-m3"
BGE_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45

ADB_VIEW_COUNT = 18
ADB_STEPS = 200
ADB_LEARNING_RATE = 0.05
ADB_BETA1 = 0.9
ADB_BETA2 = 0.999
ADB_EPS = 1e-8
ADB_INITIAL_DELTA_HAT = 0.0
ADB_SEED = 20260928

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")

LEAF_VERBS: dict[str, dict[str, str]] = {
    "search": {
        "en": "search for",
        "ko": "검색해줘",
        "es": "busca",
        "ja": "検索して",
        "de": "suche nach",
        "mixed": "search해줘",
    },
    "retrieve": {
        "en": "retrieve",
        "ko": "가져와줘",
        "es": "recupera",
        "ja": "取得して",
        "de": "rufe ab",
        "mixed": "retrieve해줘",
    },
    "list": {
        "en": "list",
        "ko": "목록으로 보여줘",
        "es": "lista",
        "ja": "一覧表示して",
        "de": "liste auf",
        "mixed": "list해줘",
    },
    "create": {
        "en": "create",
        "ko": "새로 만들어줘",
        "es": "crea",
        "ja": "作成して",
        "de": "erstelle",
        "mixed": "create해줘",
    },
    "update": {
        "en": "update",
        "ko": "수정해줘",
        "es": "actualiza",
        "ja": "更新して",
        "de": "aktualisiere",
        "mixed": "update해줘",
    },
    "delete": {
        "en": "delete",
        "ko": "삭제해줘",
        "es": "elimina",
        "ja": "削除して",
        "de": "lösche",
        "mixed": "delete해줘",
    },
    "cancel": {
        "en": "cancel",
        "ko": "취소해줘",
        "es": "cancela",
        "ja": "キャンセルして",
        "de": "storniere",
        "mixed": "cancel해줘",
    },
    "refund": {
        "en": "refund",
        "ko": "환불해줘",
        "es": "reembolsa",
        "ja": "返金して",
        "de": "erstatte",
        "mixed": "refund해줘",
    },
    "send": {
        "en": "send",
        "ko": "보내줘",
        "es": "envía",
        "ja": "送信して",
        "de": "sende",
        "mixed": "send해줘",
    },
    "share": {
        "en": "share access to",
        "ko": "공유해줘",
        "es": "comparte el acceso a",
        "ja": "共有して",
        "de": "teile den Zugriff auf",
        "mixed": "share해줘",
    },
    "export": {
        "en": "export",
        "ko": "내보내줘",
        "es": "exporta",
        "ja": "エクスポートして",
        "de": "exportiere",
        "mixed": "export해줘",
    },
    "translate": {
        "en": "translate",
        "ko": "번역해줘",
        "es": "traduce",
        "ja": "翻訳して",
        "de": "übersetze",
        "mixed": "translate해줘",
    },
    "summarize": {
        "en": "summarize",
        "ko": "요약해줘",
        "es": "resume",
        "ja": "要約して",
        "de": "fasse zusammen",
        "mixed": "summarize해줘",
    },
    "compare": {
        "en": "compare",
        "ko": "비교해줘",
        "es": "compara",
        "ja": "比較して",
        "de": "vergleiche",
        "mixed": "compare해줘",
    },
    "merge": {
        "en": "merge",
        "ko": "병합해줘",
        "es": "fusiona",
        "ja": "統合して",
        "de": "führe zusammen",
        "mixed": "merge해줘",
    },
    "restart": {
        "en": "restart",
        "ko": "재시작해줘",
        "es": "reinicia",
        "ja": "再起動して",
        "de": "starte neu",
        "mixed": "restart해줘",
    },
    "execute": {
        "en": "execute",
        "ko": "실행해줘",
        "es": "ejecuta",
        "ja": "実行して",
        "de": "führe aus",
        "mixed": "execute해줘",
    },
    "forecast": {
        "en": "forecast",
        "ko": "예측해줘",
        "es": "pronostica",
        "ja": "予測して",
        "de": "prognostiziere",
        "mixed": "forecast해줘",
    },
}

SURFACE_WRAPPERS: dict[str, tuple[str, str]] = {
    "en": ("{verb} {resource}", "please {verb} {resource}"),
    "ko": ("{resource} {verb}", "{resource} 좀 {verb}"),
    "es": ("{verb} {resource}", "por favor, {verb} {resource}"),
    "ja": ("{resource}を{verb}", "{resource}をお願いします、{verb}"),
    "de": ("{verb} {resource}", "bitte {verb} {resource}"),
    "mixed": ("{resource} {verb}", "please {resource} {verb}"),
}

CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "search": ("search", "find", "query", "검색", "찾기", "buscar", "検索", "suchen"),
    "retrieve": ("retrieve", "lookup", "look up", "fetch", "details", "조회", "불러", "obtener", "取得", "abrufen"),
    "list": ("list", "enumerate", "all available", "목록", "listar", "一覧", "auflisten"),
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
    "restart": ("restart", "reboot", "재시작", "재부팅", "reiniciar", "再起動", "neustarten"),
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


@dataclass(frozen=True)
class EndpointBoundary:
    route_id: str
    tool_key: str
    leaf: str
    center: tuple[float, ...]
    radius: float
    view_count: int
    positive_views: tuple[str, ...]


def _normalize_text(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _contains(text: str, phrase: str) -> bool:
    haystack = _normalize_text(text)
    needle = _normalize_text(phrase)
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

    if method in {"GET", "HEAD", "OPTIONS"} or endpoint.read_only is True:
        return "retrieve"
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
    result: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            result[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                leaf=infer_endpoint_leaf(endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return result


def resource_anchor(tool: Any, endpoint: Any) -> str:
    base = _normalize_text(str(tool.key or tool.name or "resource"))
    fields = [
        _normalize_text(str(field.semantic_id or field.name))
        for field in endpoint.output_fields
        if not field.identifier and str(field.semantic_id or field.name).strip()
    ]
    fields = list(dict.fromkeys(value for value in fields if value))
    if fields:
        return " ".join([base, *fields])

    parameters = [
        _normalize_text(str(parameter.name))
        for parameter in endpoint.parameters
        if str(parameter.name).strip()
    ]
    parameters = list(dict.fromkeys(value for value in parameters if value))
    if parameters:
        return " ".join([base, *parameters])
    return base


def _structural_views(tool: Any, endpoint: Any, anchor: str) -> tuple[str, str, str]:
    method = str(endpoint.method).upper() if endpoint.method else "UNSPECIFIED"
    if endpoint.read_only is True:
        access = "read-only"
    elif endpoint.read_only is False:
        access = "state-changing"
    else:
        access = "access mode unspecified"

    if endpoint.destructive is True:
        safety = "destructive"
    elif endpoint.destructive is False:
        safety = "non-destructive"
    else:
        safety = "destructive status unspecified"

    return (
        f"Registered {method} operation for {anchor}.",
        f"Registered {access} operation for {anchor}.",
        f"Registered {safety} operation for {anchor}.",
    )


def schema_positive_views(tool: Any, endpoint: Any) -> tuple[str, ...]:
    """Build exactly 18 preregistered positive views or return UNKNOWN via empty tuple."""
    endpoint_description = " ".join(str(endpoint.description or "").split())
    tool_description = " ".join(str(tool.description or "").split())
    leaf = infer_endpoint_leaf(endpoint)
    if not endpoint_description or not tool_description or leaf is None:
        return ()

    anchor = resource_anchor(tool, endpoint)
    fields = [
        str(field.semantic_id or field.name).strip()
        for field in endpoint.output_fields
        if not field.identifier and str(field.semantic_id or field.name).strip()
    ]
    fields = list(dict.fromkeys(fields))
    field_or_anchor = ", ".join(fields) if fields else anchor

    views: list[str] = [
        endpoint_description,
        f"{tool_description}. {endpoint_description}.",
        f"{endpoint_description}. Returned data or resource: {field_or_anchor}.",
    ]

    for language in LANGUAGES:
        verb = LEAF_VERBS[leaf][language]
        for template in SURFACE_WRAPPERS[language]:
            views.append(
                template.format(
                    verb=verb,
                    resource=anchor,
                )
            )

    views.extend(_structural_views(tool, endpoint, anchor))
    normalized = tuple(" ".join(view.split()) for view in views if view.strip())
    if len(normalized) != ADB_VIEW_COUNT:
        raise AssertionError(
            f"expected {ADB_VIEW_COUNT} positive-view slots, got {len(normalized)}"
        )
    if len(set(normalized)) != ADB_VIEW_COUNT:
        return ()
    return normalized


def _softplus(value: float) -> float:
    if value > 30.0:
        return value
    if value < -30.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def learn_adb_radius(
    distances: list[float],
    *,
    steps: int = ADB_STEPS,
    learning_rate: float = ADB_LEARNING_RATE,
) -> float:
    if not distances:
        raise ValueError("ADB radius requires positive distances")
    if any(not math.isfinite(value) or value < 0.0 for value in distances):
        raise ValueError("ADB distances must be finite and non-negative")
    if steps <= 0 or learning_rate <= 0.0:
        raise ValueError("ADB optimizer configuration must be positive")

    delta_hat = ADB_INITIAL_DELTA_HAT
    first_moment = 0.0
    second_moment = 0.0

    for step in range(1, steps + 1):
        radius = _softplus(delta_hat)
        radius_gradient = sum(
            1.0 if distance <= radius else -1.0
            for distance in distances
        ) / len(distances)
        gradient = radius_gradient * _sigmoid(delta_hat)

        first_moment = (
            ADB_BETA1 * first_moment
            + (1.0 - ADB_BETA1) * gradient
        )
        second_moment = (
            ADB_BETA2 * second_moment
            + (1.0 - ADB_BETA2) * gradient * gradient
        )
        first_unbiased = first_moment / (1.0 - ADB_BETA1**step)
        second_unbiased = second_moment / (1.0 - ADB_BETA2**step)
        delta_hat -= learning_rate * first_unbiased / (
            math.sqrt(second_unbiased) + ADB_EPS
        )

    radius = _softplus(delta_hat)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("learned ADB radius must be finite and positive")
    return radius


def _normalize_vector(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values:
        raise ValueError("embedding vector must not be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedding vector contains non-finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / norm for value in values]


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [_normalize_vector(vector) for vector in raw]
    if not vectors:
        raise ValueError("embedder returned no vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    return vectors


def _mean_center(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise ValueError("center requires vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("center vectors must align")
    mean = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(width)
    ]
    return _normalize_vector(mean)


def _euclidean(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values) or not left_values:
        raise ValueError("distance vectors must align")
    return math.sqrt(
        sum(
            (a - b) * (a - b)
            for a, b in zip(left_values, right_values, strict=True)
        )
    )


def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = _normalize_vector(left)
    right_values = _normalize_vector(right)
    return max(
        -1.0,
        min(
            1.0,
            sum(
                a * b
                for a, b in zip(left_values, right_values, strict=True)
            ),
        ),
    )


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
        dict.fromkeys(
            part
            for part in [operation_name, *aliases, fallback]
            if part
        )
    )


class SchemaDerivedADBRouter:
    """Frozen BGE positive routing plus schema-derived positive-only ADB veto."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        endpoint_lookup: dict[str, tuple[Any, Any]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
                endpoint_lookup[route_id] = (tool, endpoint)

        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_texts = [
            *(route_specs[route][0] for route in self.route_ids),
            *(route_specs[route][1] for route in self.route_ids),
        ]
        route_vectors = _to_vectors(embedder(route_texts))
        route_count = len(self.route_ids)
        if len(route_vectors) != route_count * 2:
            raise ValueError("unexpected route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, route_vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, route_vectors[route_count:], strict=True)
        )

        views_by_route = {
            route_id: schema_positive_views(*endpoint_lookup[route_id])
            for route_id in self.route_ids
        }
        flat_views: list[str] = []
        spans: dict[str, tuple[int, int]] = {}
        for route_id in self.route_ids:
            views = views_by_route[route_id]
            if len(views) != ADB_VIEW_COUNT:
                continue
            start = len(flat_views)
            flat_views.extend(views)
            spans[route_id] = (start, len(flat_views))

        view_vectors = _to_vectors(embedder(flat_views)) if flat_views else []
        if len(view_vectors) != len(flat_views):
            raise ValueError("unexpected positive-view embedding count")

        boundaries: dict[str, EndpointBoundary | None] = {}
        for route_id in self.route_ids:
            span = spans.get(route_id)
            views = views_by_route[route_id]
            contract = self.contracts[route_id]
            if span is None or contract.leaf is None:
                boundaries[route_id] = None
                continue
            start, end = span
            vectors = view_vectors[start:end]
            center = _mean_center(vectors)
            distances = [
                _euclidean(vector, center)
                for vector in vectors
            ]
            boundaries[route_id] = EndpointBoundary(
                route_id=route_id,
                tool_key=contract.tool_key,
                leaf=contract.leaf,
                center=tuple(center),
                radius=learn_adb_radius(distances),
                view_count=len(views),
                positive_views=views,
            )
        self.boundaries = boundaries

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
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_routes = [
            route_id
            for route_id in self.route_ids
            if self.contracts[route_id].tool_key == raw_tool
        ]
        missing_boundary = any(
            self.boundaries[route_id] is None
            for route_id in tool_routes
        )

        diagnostics: list[dict[str, Any]] = []
        inside_routes: list[str] = []
        if missing_boundary:
            predicted = raw_top_route
            reason = "unknown_boundary_preserve"
        else:
            for route_id in tool_routes:
                boundary = self.boundaries[route_id]
                if boundary is None:
                    raise AssertionError("boundary disappeared after completeness check")
                distance = _euclidean(query_vector, boundary.center)
                ratio = distance / boundary.radius
                inside = distance <= boundary.radius
                if inside:
                    inside_routes.append(route_id)
                diagnostics.append(
                    {
                        "route_id": route_id,
                        "distance": distance,
                        "radius": boundary.radius,
                        "boundary_ratio": ratio,
                        "inside": inside,
                        "view_count": boundary.view_count,
                    }
                )
            if inside_routes:
                predicted = raw_top_route
                reason = "inside_registered_boundary_preserve"
            else:
                predicted = None
                reason = "outside_all_registered_boundaries"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_routes": tool_routes,
            "inside_routes": inside_routes,
            "boundary_diagnostics": diagnostics,
            "missing_boundary": missing_boundary,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
