# ruff: noqa: E501
"""Schema-derived Adaptive Decision Boundary baseline for experiment #384.

This research adapter preserves frozen BGE-M3 as the sole positive selector. Registry-derived
synthetic positives define endpoint capability centroids and ADB-style spherical boundaries.
Boundaries may only preserve the raw route or veto to NO_ROUTE.
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

ADB_STEPS = 200
ADB_LR = 0.05
ADB_BETA1 = 0.9
ADB_BETA2 = 0.999
ADB_EPS = 1e-8

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")

ACTION_PHRASES: dict[str, dict[str, str]] = {
    "search": {
        "en": "search unknown matching items by criteria",
        "ko": "조건에 맞는 미지의 항목을 검색",
        "es": "buscar elementos desconocidos que coincidan con criterios",
        "ja": "条件に合う未知の項目を検索",
        "de": "unbekannte passende Elemente nach Kriterien suchen",
        "mixed": "criteria로 unknown items 검색",
    },
    "retrieve": {
        "en": "retrieve one already identified existing item",
        "ko": "이미 식별된 기존 항목 하나를 조회",
        "es": "recuperar un elemento existente ya identificado",
        "ja": "既に特定された既存項目一件を取得",
        "de": "ein bereits identifiziertes vorhandenes Element abrufen",
        "mixed": "known existing item 하나 retrieve",
    },
    "list": {
        "en": "list a collection of existing items",
        "ko": "기존 항목 컬렉션을 목록으로 조회",
        "es": "listar una colección de elementos existentes",
        "ja": "既存項目の集合を一覧表示",
        "de": "eine Sammlung vorhandener Elemente auflisten",
        "mixed": "existing collection을 list",
    },
    "create": {
        "en": "create a brand-new resource",
        "ko": "새 리소스를 생성",
        "es": "crear un recurso completamente nuevo",
        "ja": "新しいリソースを作成",
        "de": "eine neue Ressource erstellen",
        "mixed": "brand-new resource create",
    },
    "update": {
        "en": "update fields or settings of an existing resource",
        "ko": "기존 리소스의 필드나 설정을 수정",
        "es": "actualizar campos o ajustes de un recurso existente",
        "ja": "既存リソースの項目や設定を更新",
        "de": "Felder oder Einstellungen einer bestehenden Ressource aktualisieren",
        "mixed": "existing resource fields update",
    },
    "delete": {
        "en": "permanently delete an existing resource",
        "ko": "기존 리소스를 영구 삭제",
        "es": "eliminar permanentemente un recurso existente",
        "ja": "既存リソースを永久削除",
        "de": "eine bestehende Ressource dauerhaft löschen",
        "mixed": "existing resource permanently delete",
    },
    "cancel": {
        "en": "cancel or stop an active request or process",
        "ko": "진행 중인 요청이나 프로세스를 취소",
        "es": "cancelar o detener una solicitud o proceso activo",
        "ja": "進行中の依頼や処理を取り消す",
        "de": "eine aktive Anfrage oder einen Prozess stornieren",
        "mixed": "active request process cancel",
    },
    "refund": {
        "en": "refund money for a payment or completed transaction",
        "ko": "결제나 완료 거래 금액을 환불",
        "es": "reembolsar dinero por un pago o transacción completada",
        "ja": "支払いまたは完了取引の金銭を返金",
        "de": "Geld für eine Zahlung oder abgeschlossene Transaktion erstatten",
        "mixed": "payment transaction money refund",
    },
    "send": {
        "en": "send or deliver an item or message to a destination",
        "ko": "항목이나 메시지를 목적지로 전송",
        "es": "enviar o entregar un elemento o mensaje a un destino",
        "ja": "項目やメッセージを宛先へ送信",
        "de": "ein Element oder eine Nachricht an ein Ziel senden",
        "mixed": "item message destination으로 send",
    },
    "share": {
        "en": "share access to an existing resource with another user",
        "ko": "기존 리소스 접근권을 다른 사용자와 공유",
        "es": "compartir acceso a un recurso existente con otro usuario",
        "ja": "既存リソースへのアクセスを別ユーザーと共有",
        "de": "Zugriff auf eine bestehende Ressource mit einem anderen Nutzer teilen",
        "mixed": "existing resource access share",
    },
    "export": {
        "en": "export or download existing data as an external file",
        "ko": "기존 데이터를 외부 파일로 내보내기",
        "es": "exportar o descargar datos existentes como archivo externo",
        "ja": "既存データを外部ファイルとして出力",
        "de": "bestehende Daten als externe Datei exportieren",
        "mixed": "existing data external file export",
    },
    "translate": {
        "en": "translate content into another human language",
        "ko": "콘텐츠를 다른 언어로 번역",
        "es": "traducir contenido a otro idioma humano",
        "ja": "コンテンツを別の人間言語へ翻訳",
        "de": "Inhalt in eine andere menschliche Sprache übersetzen",
        "mixed": "content 다른 language로 translate",
    },
    "summarize": {
        "en": "summarize content into its main points",
        "ko": "콘텐츠를 핵심 내용으로 요약",
        "es": "resumir contenido en sus puntos principales",
        "ja": "コンテンツを要点に要約",
        "de": "Inhalt auf seine Hauptpunkte zusammenfassen",
        "mixed": "content main points summarize",
    },
    "compare": {
        "en": "compare multiple items for similarities or differences",
        "ko": "여러 항목의 공통점이나 차이점을 비교",
        "es": "comparar varios elementos por similitudes o diferencias",
        "ja": "複数項目の共通点や違いを比較",
        "de": "mehrere Elemente auf Gemeinsamkeiten oder Unterschiede vergleichen",
        "mixed": "multiple items differences compare",
    },
    "merge": {
        "en": "merge multiple resources into one result",
        "ko": "여러 리소스를 하나의 결과로 병합",
        "es": "fusionar varios recursos en un solo resultado",
        "ja": "複数リソースを一つの結果へ統合",
        "de": "mehrere Ressourcen zu einem Ergebnis zusammenführen",
        "mixed": "multiple resources one result merge",
    },
    "restart": {
        "en": "restart or reboot an existing machine service or job",
        "ko": "기존 장비 서비스 작업을 재시작",
        "es": "reiniciar una máquina servicio o trabajo existente",
        "ja": "既存の機器サービスジョブを再起動",
        "de": "eine vorhandene Maschine einen Dienst oder Job neu starten",
        "mixed": "existing machine service job restart",
    },
    "execute": {
        "en": "execute or launch a registered workflow or operation",
        "ko": "등록된 워크플로나 작업을 실행",
        "es": "ejecutar o lanzar un flujo u operación registrada",
        "ja": "登録済みワークフローや操作を実行",
        "de": "einen registrierten Workflow oder eine Operation ausführen",
        "mixed": "registered workflow operation execute",
    },
    "forecast": {
        "en": "forecast a future value state trend or outcome",
        "ko": "미래 값 상태 추세 결과를 예측",
        "es": "pronosticar un valor estado tendencia o resultado futuro",
        "ja": "将来の値状態傾向結果を予測",
        "de": "einen zukünftigen Wert Zustand Trend oder Ausgang vorhersagen",
        "mixed": "future value state trend forecast",
    },
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

METHOD_LEAF = {"PATCH": "update", "PUT": "update", "DELETE": "delete"}


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    leaf: str | None
    resource_anchor: str
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]
    synthetic_positives: tuple[str, ...]


@dataclass(frozen=True)
class AdbBoundary:
    route_id: str
    tool_key: str
    leaf: str
    centroid: tuple[float, ...]
    radius: float
    synthetic_count: int
    distances: tuple[float, ...]


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
                    normalization.canonical_unit if normalization is not None else None
                ),
                "dimension": normalization.dimension if normalization is not None else None,
                "scale": normalization.scale if normalization is not None else None,
                "offset": normalization.offset if normalization is not None else None,
                "qualifiers": dict(field.qualifiers),
                "identifier": bool(field.identifier),
            }
        )
    return tuple(rows)


def _resource_anchor(tool: Any, endpoint: Any) -> str:
    base = _normalize(str(tool.key or tool.name))
    fields = [
        _normalize(str(field.semantic_id or field.name))
        for field in endpoint.output_fields
        if not field.identifier
    ]
    if not fields:
        fields = [
            _normalize(str(parameter.name))
            for parameter in endpoint.parameters
        ]
    selected = [item for item in fields if item][:2]
    return " ".join(dict.fromkeys([base, *selected])).strip()


def synthetic_positive_texts(
    *,
    tool: Any,
    endpoint: Any,
    leaf: str,
) -> tuple[str, ...]:
    """Return the exact 18 preregistered schema-only positive views or UNKNOWN."""
    resource = _resource_anchor(tool, endpoint)
    description = " ".join(str(endpoint.description or "").split())
    tool_description = " ".join(str(tool.description or "").split())
    if not description or not tool_description or not resource:
        return ()

    field_labels = [
        str(field.semantic_id or field.name).strip()
        for field in endpoint.output_fields
        if not field.identifier and str(field.semantic_id or field.name).strip()
    ]
    field_labels = list(dict.fromkeys(field_labels))
    field_or_resource = ", ".join(field_labels) if field_labels else resource

    rows = [
        description,
        f"{tool_description}. {description}.",
        f"{description}. Returned data or resource: {field_or_resource}.",
    ]

    for language in LANGUAGES:
        phrase = ACTION_PHRASES[leaf][language]
        rows.append(f"{phrase}: {resource}")
        rows.append(f"{resource}: {phrase}")

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

    rows.extend(
        [
            f"Registered {method} operation for {resource}.",
            f"Registered {access} operation for {resource}.",
            f"Registered {safety} operation for {resource}.",
        ]
    )

    normalized = tuple(" ".join(row.split()) for row in rows if row.strip())
    if len(normalized) != 18:
        raise AssertionError(f"expected 18 synthetic positives, got {len(normalized)}")
    if len(set(normalized)) != 18:
        return ()
    return normalized


def compile_registry_contracts(registry: Any) -> dict[str, RouteContract]:
    contracts: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            leaf = infer_endpoint_leaf(endpoint)
            contracts[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                leaf=leaf,
                resource_anchor=_resource_anchor(tool, endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
                synthetic_positives=(
                    synthetic_positive_texts(tool=tool, endpoint=endpoint, leaf=leaf)
                    if leaf is not None
                    else ()
                ),
            )
    return contracts


def _softplus(value: float) -> float:
    if value > 20.0:
        return value
    if value < -20.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def learn_adb_radius(distances: Iterable[float]) -> float:
    """Learn the ADB radius with deterministic scalar Adam over the original boundary loss."""
    values = [float(value) for value in distances]
    if not values:
        raise ValueError("ADB requires at least one positive distance")
    if any(value < 0.0 or not math.isfinite(value) for value in values):
        raise ValueError("ADB distances must be finite and non-negative")

    theta = 0.0
    first_moment = 0.0
    second_moment = 0.0
    for step in range(1, ADB_STEPS + 1):
        radius = _softplus(theta)
        signs = [
            -1.0 if distance > radius else 1.0
            for distance in values
        ]
        grad_radius = sum(signs) / len(signs)
        grad_theta = grad_radius * _sigmoid(theta)

        first_moment = ADB_BETA1 * first_moment + (1.0 - ADB_BETA1) * grad_theta
        second_moment = (
            ADB_BETA2 * second_moment
            + (1.0 - ADB_BETA2) * grad_theta * grad_theta
        )
        m_hat = first_moment / (1.0 - ADB_BETA1**step)
        v_hat = second_moment / (1.0 - ADB_BETA2**step)
        theta -= ADB_LR * m_hat / (math.sqrt(v_hat) + ADB_EPS)

    return _softplus(theta)


def _euclidean(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("vectors must align")
    return math.sqrt(
        sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True))
    )


def _centroid(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise ValueError("centroid requires vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("vectors must have consistent dimensions")
    mean = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(width)
    ]
    return _normalize_vector(mean)


def _normalize_vector(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values:
        raise ValueError("embedding vector must not be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedder returned non-finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / norm for value in values]


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [_normalize_vector(vector) for vector in raw]
    if not vectors:
        raise ValueError("embedder returned empty vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    return vectors


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("vectors must have non-zero norm")
    return max(
        -1.0,
        min(
            1.0,
            sum(a * b for a, b in zip(left, right, strict=True))
            / (left_norm * right_norm),
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
        dict.fromkeys(part for part in [operation_name, *aliases, fallback] if part)
    )


class SchemaAdbRouter:
    """Frozen BGE positive routing plus schema-derived ADB membership rejection."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        tool_by_route: dict[str, Any] = {}
        endpoint_by_route: dict[str, Any] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
                tool_by_route[route_id] = tool
                endpoint_by_route[route_id] = endpoint

        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_count = len(self.route_ids)
        route_vectors = _to_vectors(
            embedder(
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

        self.boundaries: dict[str, AdbBoundary] = {}
        for route_id in self.route_ids:
            contract = self.contracts[route_id]
            positives = list(contract.synthetic_positives)
            if contract.leaf is None or len(positives) != 18:
                continue
            vectors = _to_vectors(embedder(positives))
            center = _centroid(vectors)
            distances = [_euclidean(vector, center) for vector in vectors]
            radius = learn_adb_radius(distances)
            self.boundaries[route_id] = AdbBoundary(
                route_id=route_id,
                tool_key=contract.tool_key,
                leaf=contract.leaf,
                centroid=tuple(center),
                radius=radius,
                synthetic_count=len(positives),
                distances=tuple(distances),
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
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_contracts = [
            contract
            for contract in self.contracts.values()
            if contract.tool_key == raw_tool
        ]
        tool_has_unknown = any(
            contract.leaf is None or contract.route_id not in self.boundaries
            for contract in tool_contracts
        )

        boundary_rows: list[dict[str, Any]] = []
        if tool_has_unknown:
            predicted = raw_top_route
            reason = "unknown_endpoint_semantics_preserve"
        else:
            for contract in tool_contracts:
                boundary = self.boundaries[contract.route_id]
                distance = _euclidean(query_vector, boundary.centroid)
                boundary_rows.append(
                    {
                        "route_id": boundary.route_id,
                        "leaf": boundary.leaf,
                        "distance": distance,
                        "radius": boundary.radius,
                        "inside": distance <= boundary.radius,
                    }
                )
            if any(row["inside"] for row in boundary_rows):
                predicted = raw_top_route
                reason = "inside_registered_capability_boundary"
            else:
                predicted = None
                reason = "outside_all_registered_capability_boundaries"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_leaf": tool_has_unknown,
            "boundary_rows": boundary_rows,
            "inside_boundary_count": sum(bool(row["inside"]) for row in boundary_rows),
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in raw_ranked
            ],
        }
