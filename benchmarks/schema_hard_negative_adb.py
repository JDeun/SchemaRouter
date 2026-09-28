# ruff: noqa: E501
"""Schema-derived hard-negative adaptive boundary for experiment #393.

The positive representation is inherited unchanged from the frozen #384 ADB baseline.
Hard negatives are generated only from the registered tool's missing operation leaves while
preserving each endpoint's schema-derived resource anchor. Frozen BGE-M3 remains the sole positive
route selector; this boundary may only preserve that winner or veto to NO_ROUTE.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from benchmarks.schema_adb_baseline import (
    ACTION_PHRASES,
    ADB_BETA1,
    ADB_BETA2,
    ADB_EPS,
    ADB_LR,
    ADB_STEPS,
    ACTION_WEIGHT,
    BGE_MODEL,
    BGE_REVISION,
    SCHEMA_WEIGHT,
    RouteContract,
    _action_text,
    _centroid,
    _cosine,
    _euclidean,
    _schema_text,
    _sigmoid,
    _softplus,
    _to_vectors,
    compile_registry_contracts,
)

LEAF_ORDER = tuple(ACTION_PHRASES)

HARD_NEGATIVE_PHRASES: dict[str, dict[str, str]] = {
    "search": {
        "en": "locate matching {resource} by criteria",
        "ko": "조건에 맞는 {resource} 항목을 찾아보기",
        "es": "localizar {resource} que coincida con criterios",
        "ja": "条件に一致する{resource}を探す",
        "de": "passende {resource} nach Kriterien finden",
        "mixed": "criteria에 맞는 {resource} locate하기",
    },
    "retrieve": {
        "en": "load one identified {resource}",
        "ko": "식별된 {resource} 하나를 불러오기",
        "es": "cargar un {resource} ya identificado",
        "ja": "特定済みの{resource}を一件読み込む",
        "de": "ein identifiziertes {resource} laden",
        "mixed": "identified {resource} 하나 load하기",
    },
    "list": {
        "en": "enumerate the complete set of {resource}",
        "ko": "{resource} 전체 집합을 나열하기",
        "es": "enumerar el conjunto completo de {resource}",
        "ja": "{resource}の全件を列挙する",
        "de": "die vollständige Menge von {resource} aufzählen",
        "mixed": "{resource} complete set enumerate하기",
    },
    "create": {
        "en": "register one new {resource}",
        "ko": "새 {resource} 하나를 등록하기",
        "es": "registrar un {resource} nuevo",
        "ja": "新しい{resource}を一件登録する",
        "de": "ein neues {resource} registrieren",
        "mixed": "new {resource} 하나 register하기",
    },
    "update": {
        "en": "revise stored {resource}",
        "ko": "저장된 {resource} 내용을 고치기",
        "es": "revisar el {resource} almacenado",
        "ja": "保存済みの{resource}を修正する",
        "de": "gespeichertes {resource} überarbeiten",
        "mixed": "stored {resource} revise하기",
    },
    "delete": {
        "en": "erase existing {resource} permanently",
        "ko": "기존 {resource}를 영구적으로 지우기",
        "es": "borrar permanentemente el {resource} existente",
        "ja": "既存の{resource}を永久に消去する",
        "de": "bestehendes {resource} dauerhaft entfernen",
        "mixed": "existing {resource} permanently erase하기",
    },
    "cancel": {
        "en": "terminate active {resource}",
        "ko": "진행 중인 {resource}를 중단하기",
        "es": "terminar el {resource} activo",
        "ja": "進行中の{resource}を中止する",
        "de": "aktives {resource} beenden",
        "mixed": "active {resource} terminate하기",
    },
    "refund": {
        "en": "return the payment for {resource}",
        "ko": "{resource}의 결제금을 돌려주기",
        "es": "devolver el pago de {resource}",
        "ja": "{resource}の支払いを返金する",
        "de": "die Zahlung für {resource} zurückerstatten",
        "mixed": "{resource} payment return하기",
    },
    "send": {
        "en": "dispatch {resource} to a destination",
        "ko": "{resource}를 목적지로 발송하기",
        "es": "despachar {resource} a un destino",
        "ja": "{resource}を宛先へ発送する",
        "de": "{resource} an ein Ziel versenden",
        "mixed": "{resource} destination으로 dispatch하기",
    },
    "share": {
        "en": "grant another user access to {resource}",
        "ko": "다른 사용자에게 {resource} 접근권을 부여하기",
        "es": "conceder a otro usuario acceso a {resource}",
        "ja": "別ユーザーに{resource}へのアクセスを付与する",
        "de": "einem anderen Nutzer Zugriff auf {resource} gewähren",
        "mixed": "another user에게 {resource} access grant하기",
    },
    "export": {
        "en": "write {resource} to an external file",
        "ko": "{resource}를 외부 파일로 기록하기",
        "es": "guardar {resource} en un archivo externo",
        "ja": "{resource}を外部ファイルへ書き出す",
        "de": "{resource} in eine externe Datei schreiben",
        "mixed": "{resource} external file로 write하기",
    },
    "translate": {
        "en": "render {resource} in a different human language",
        "ko": "{resource}를 다른 사람 언어로 옮기기",
        "es": "pasar {resource} a otro idioma humano",
        "ja": "{resource}を別の人間言語に置き換える",
        "de": "{resource} in eine andere menschliche Sprache übertragen",
        "mixed": "{resource} different language로 render하기",
    },
    "summarize": {
        "en": "condense {resource} to its key points",
        "ko": "{resource}를 핵심 요점으로 압축하기",
        "es": "condensar {resource} a sus puntos clave",
        "ja": "{resource}を重要点に圧縮する",
        "de": "{resource} auf die Kernpunkte verdichten",
        "mixed": "{resource} key points로 condense하기",
    },
    "compare": {
        "en": "contrast multiple {resource} items",
        "ko": "여러 {resource} 항목의 차이를 대조하기",
        "es": "contrastar varios elementos de {resource}",
        "ja": "複数の{resource}項目を対比する",
        "de": "mehrere {resource}-Elemente gegenüberstellen",
        "mixed": "multiple {resource} items contrast하기",
    },
    "merge": {
        "en": "combine multiple {resource} items into one result",
        "ko": "여러 {resource} 항목을 하나의 결과로 합치기",
        "es": "combinar varios {resource} en un solo resultado",
        "ja": "複数の{resource}を一つの結果へ結合する",
        "de": "mehrere {resource}-Elemente zu einem Ergebnis kombinieren",
        "mixed": "multiple {resource} items one result로 combine하기",
    },
    "restart": {
        "en": "reboot existing {resource}",
        "ko": "기존 {resource}를 다시 기동하기",
        "es": "reiniciar el {resource} existente",
        "ja": "既存の{resource}を再起動する",
        "de": "bestehendes {resource} neu starten",
        "mixed": "existing {resource} reboot하기",
    },
    "execute": {
        "en": "invoke registered {resource}",
        "ko": "등록된 {resource}를 호출해 실행하기",
        "es": "invocar el {resource} registrado",
        "ja": "登録済みの{resource}を呼び出して実行する",
        "de": "registriertes {resource} aufrufen",
        "mixed": "registered {resource} invoke하기",
    },
    "forecast": {
        "en": "project future {resource}",
        "ko": "향후 {resource} 값을 전망하기",
        "es": "proyectar el {resource} futuro",
        "ja": "将来の{resource}を見通す",
        "de": "zukünftiges {resource} prognostizieren",
        "mixed": "future {resource} project하기",
    },
}


@dataclass(frozen=True)
class HardNegativeBoundary:
    route_id: str
    tool_key: str
    leaf: str
    centroid: tuple[float, ...]
    radius: float
    positive_count: int
    hard_negative_count: int
    positive_distances: tuple[float, ...]
    hard_negative_distances: tuple[float, ...]


def hard_negative_texts(
    contract: RouteContract,
    *,
    tool_supported_leaves: set[str],
) -> tuple[str, ...]:
    """Generate same-resource hard negatives from the registered capability complement."""
    if contract.leaf is None or not contract.resource_anchor:
        return ()
    absent_leaves = [
        leaf
        for leaf in LEAF_ORDER
        if leaf not in tool_supported_leaves
    ]
    if not absent_leaves:
        return ()

    rows = [
        HARD_NEGATIVE_PHRASES[leaf][language].format(
            resource=contract.resource_anchor
        )
        for leaf in absent_leaves
        for language in ("en", "ko", "es", "ja", "de", "mixed")
    ]
    normalized = tuple(" ".join(row.split()) for row in rows if row.strip())
    if len(normalized) != len(absent_leaves) * 6:
        raise AssertionError("hard-negative bank has an unexpected row count")
    if len(set(normalized)) != len(normalized):
        return ()
    return normalized


def learn_hard_negative_radius(
    positive_distances: Iterable[float],
    hard_negative_distances: Iterable[float],
) -> float:
    """Fit the exact preregistered balanced positive/hard-negative radial hinge."""
    positive = [float(value) for value in positive_distances]
    negative = [float(value) for value in hard_negative_distances]
    if not positive or not negative:
        raise ValueError("hard-negative boundary needs positive and negative distances")
    if any(
        value < 0.0 or not math.isfinite(value)
        for value in [*positive, *negative]
    ):
        raise ValueError("boundary distances must be finite and non-negative")

    theta = 0.0
    first_moment = 0.0
    second_moment = 0.0

    for step in range(1, ADB_STEPS + 1):
        radius = _softplus(theta)
        positive_gradient = -(
            sum(distance > radius for distance in positive) / len(positive)
        )
        negative_gradient = (
            sum(distance < radius for distance in negative) / len(negative)
        )
        grad_radius = positive_gradient + negative_gradient
        grad_theta = grad_radius * _sigmoid(theta)

        first_moment = (
            ADB_BETA1 * first_moment
            + (1.0 - ADB_BETA1) * grad_theta
        )
        second_moment = (
            ADB_BETA2 * second_moment
            + (1.0 - ADB_BETA2) * grad_theta * grad_theta
        )
        first_unbiased = first_moment / (1.0 - ADB_BETA1**step)
        second_unbiased = second_moment / (1.0 - ADB_BETA2**step)
        theta -= ADB_LR * first_unbiased / (
            math.sqrt(second_unbiased) + ADB_EPS
        )

    radius = _softplus(theta)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("learned radius must be finite and positive")
    return radius


class SchemaHardNegativeAdbRouter:
    """Frozen BGE positive routing plus schema-derived hard-negative radial veto."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
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

        tool_leaves: dict[str, set[str]] = {}
        for contract in self.contracts.values():
            if contract.leaf is not None:
                tool_leaves.setdefault(contract.tool_key, set()).add(contract.leaf)

        positives_by_route = {
            route_id: tuple(self.contracts[route_id].synthetic_positives)
            for route_id in self.route_ids
        }
        negatives_by_route = {
            route_id: hard_negative_texts(
                self.contracts[route_id],
                tool_supported_leaves=tool_leaves.get(
                    self.contracts[route_id].tool_key,
                    set(),
                ),
            )
            for route_id in self.route_ids
        }

        flat_texts: list[str] = []
        spans: dict[str, tuple[int, int, int]] = {}
        for route_id in self.route_ids:
            positives = positives_by_route[route_id]
            negatives = negatives_by_route[route_id]
            if len(positives) != 18 or not negatives:
                continue
            start = len(flat_texts)
            flat_texts.extend(positives)
            split = len(flat_texts)
            flat_texts.extend(negatives)
            end = len(flat_texts)
            spans[route_id] = (start, split, end)

        training_vectors = _to_vectors(embedder(flat_texts)) if flat_texts else []
        if len(training_vectors) != len(flat_texts):
            raise ValueError("unexpected training embedding count")

        self.boundaries: dict[str, HardNegativeBoundary] = {}
        for route_id in self.route_ids:
            span = spans.get(route_id)
            contract = self.contracts[route_id]
            if span is None or contract.leaf is None:
                continue
            start, split, end = span
            positive_vectors = training_vectors[start:split]
            negative_vectors = training_vectors[split:end]
            center = _centroid(positive_vectors)
            positive_distances = [
                _euclidean(vector, center)
                for vector in positive_vectors
            ]
            negative_distances = [
                _euclidean(vector, center)
                for vector in negative_vectors
            ]
            radius = learn_hard_negative_radius(
                positive_distances,
                negative_distances,
            )
            self.boundaries[route_id] = HardNegativeBoundary(
                route_id=route_id,
                tool_key=contract.tool_key,
                leaf=contract.leaf,
                centroid=tuple(center),
                radius=radius,
                positive_count=len(positive_vectors),
                hard_negative_count=len(negative_vectors),
                positive_distances=tuple(positive_distances),
                hard_negative_distances=tuple(negative_distances),
            )

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT * _cosine(
                    query_vector,
                    self.schema_vectors[route_id],
                )
                + ACTION_WEIGHT * _cosine(
                    query_vector,
                    self.action_vectors[route_id],
                )
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
            contract.leaf is None
            or contract.route_id not in self.boundaries
            for contract in tool_contracts
        )

        boundary_rows: list[dict[str, Any]] = []
        if tool_has_unknown:
            predicted = raw_top_route
            reason = "unknown_boundary_preserve"
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
                        "boundary_ratio": distance / boundary.radius,
                        "inside": distance <= boundary.radius,
                    }
                )
            if any(row["inside"] for row in boundary_rows):
                predicted = raw_top_route
                reason = "inside_registered_hard_negative_boundary"
            else:
                predicted = None
                reason = "outside_all_hard_negative_boundaries"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_leaf": tool_has_unknown,
            "inside_boundary_count": sum(
                bool(row["inside"])
                for row in boundary_rows
            ),
            "boundary_rows": boundary_rows,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
