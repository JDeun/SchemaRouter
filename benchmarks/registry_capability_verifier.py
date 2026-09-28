"""Generic registry-compiled verifier for preregistered experiment #338.

The learned head is fit only on a fixed generic synthetic operation corpus.  It never sees
canonical DEV labels, fresh-confirmation rows, route IDs, or evaluation-tool identities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from benchmarks.registry_capability_contract import (
    ACTION_PROTOTYPES,
    TEMPORAL_PROTOTYPES,
    CapabilityContract,
    compile_registry,
    counterfactual_action_texts,
    structural_action_compatible,
)

SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45
HEAD_RANDOM_STATE = 338

_ACTION_CLUSTER = {
    "search": "read",
    "list": "read",
    "retrieve": "read",
    "forecast": "forecast",
    "create": "create",
    "update": "update",
    "delete": "delete",
    "send": "send",
    "cancel": "cancel",
    "export": "export",
    "translate": "translate",
    "summarize": "summarize",
    "compare": "compare",
    "execute": "execute",
}

_GENERIC_ACTION_PHRASES: dict[str, dict[str, str]] = {
    "retrieve": {
        "en": "fetch {r}",
        "ko": "{r}를 조회해줘",
        "es": "recupera {r}",
        "ja": "{r}を取得して",
        "de": "hole {r}",
        "mixed": "{r}를 fetch해줘",
    },
    "search": {
        "en": "search for {r}",
        "ko": "{r}를 찾아줘",
        "es": "busca {r}",
        "ja": "{r}を探して",
        "de": "suche nach {r}",
        "mixed": "{r}를 search해줘",
    },
    "list": {
        "en": "list {r}",
        "ko": "{r} 목록을 보여줘",
        "es": "enumera {r}",
        "ja": "{r}を一覧にして",
        "de": "liste {r} auf",
        "mixed": "{r} list 보여줘",
    },
    "create": {
        "en": "create {r}",
        "ko": "{r}를 새로 만들어줘",
        "es": "crea {r}",
        "ja": "{r}を作成して",
        "de": "erstelle {r}",
        "mixed": "{r}를 create해줘",
    },
    "update": {
        "en": "update {r}",
        "ko": "{r}를 수정해줘",
        "es": "actualiza {r}",
        "ja": "{r}を更新して",
        "de": "aktualisiere {r}",
        "mixed": "{r}를 update해줘",
    },
    "delete": {
        "en": "delete {r}",
        "ko": "{r}를 삭제해줘",
        "es": "elimina {r}",
        "ja": "{r}を削除して",
        "de": "lösche {r}",
        "mixed": "{r}를 delete해줘",
    },
    "forecast": {
        "en": "forecast the future state of {r}",
        "ko": "{r}의 앞으로 상태를 예측해줘",
        "es": "pronostica el estado futuro de {r}",
        "ja": "{r}の将来の状態を予測して",
        "de": "prognostiziere den zukünftigen Zustand von {r}",
        "mixed": "{r} future state를 forecast해줘",
    },
    "send": {
        "en": "send {r}",
        "ko": "{r}를 보내줘",
        "es": "envía {r}",
        "ja": "{r}を送って",
        "de": "sende {r}",
        "mixed": "{r}를 send해줘",
    },
    "cancel": {
        "en": "cancel {r}",
        "ko": "{r}를 취소해줘",
        "es": "cancela {r}",
        "ja": "{r}をキャンセルして",
        "de": "storniere {r}",
        "mixed": "{r}를 cancel해줘",
    },
    "export": {
        "en": "export {r}",
        "ko": "{r}를 내보내줘",
        "es": "exporta {r}",
        "ja": "{r}をエクスポートして",
        "de": "exportiere {r}",
        "mixed": "{r}를 export해줘",
    },
    "translate": {
        "en": "translate {r}",
        "ko": "{r}를 번역해줘",
        "es": "traduce {r}",
        "ja": "{r}を翻訳して",
        "de": "übersetze {r}",
        "mixed": "{r}를 translate해줘",
    },
    "summarize": {
        "en": "summarize {r}",
        "ko": "{r}를 요약해줘",
        "es": "resume {r}",
        "ja": "{r}を要約して",
        "de": "fasse {r} zusammen",
        "mixed": "{r}를 summarize해줘",
    },
    "compare": {
        "en": "compare {r}",
        "ko": "{r}를 비교해줘",
        "es": "compara {r}",
        "ja": "{r}を比較して",
        "de": "vergleiche {r}",
        "mixed": "{r}를 compare해줘",
    },
    "execute": {
        "en": "run the operation for {r}",
        "ko": "{r} 작업을 실행해줘",
        "es": "ejecuta la operación para {r}",
        "ja": "{r}の操作を実行して",
        "de": "führe die Operation für {r} aus",
        "mixed": "{r} operation을 run해줘",
    },
}

_FIT_RESOURCES = (
    "shipment record",
    "sensor reading",
    "invoice record",
    "playlist entry",
    "device profile",
    "image asset",
    "reservation record",
    "audit record",
)
_CALIBRATION_RESOURCES = (
    "workspace note",
    "contract record",
    "media clip",
    "subscription entry",
)

_TEMPORAL_PHRASES = {
    "current": {
        "en": "show the current {r}",
        "ko": "현재 {r}를 보여줘",
        "es": "muestra el {r} actual",
        "ja": "現在の{r}を見せて",
        "de": "zeige den aktuellen {r}",
        "mixed": "현재 {r} 보여줘",
    },
    "future": {
        "en": "show the future {r}",
        "ko": "앞으로의 {r}를 보여줘",
        "es": "muestra el {r} futuro",
        "ja": "将来の{r}を見せて",
        "de": "zeige den zukünftigen {r}",
        "mixed": "future {r} 보여줘",
    },
    "historical": {
        "en": "show the historical {r}",
        "ko": "과거 {r}를 보여줘",
        "es": "muestra el {r} histórico",
        "ja": "過去の{r}を見せて",
        "de": "zeige den historischen {r}",
        "mixed": "historical {r} 보여줘",
    },
}

_OOD_QUERIES = (
    "write a short poem about silence",
    "prove that there are infinitely many prime numbers",
    "tell me a joke",
    "explain why the sky looks blue",
    "compose a chord progression in D minor",
    "what is the capital of a fictional kingdom",
)

Embedder = Callable[[list[str]], list[list[float]]]


def _dot(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("vectors must be non-empty and aligned")
    value = sum(a * b for a, b in zip(left, right, strict=True))
    if not math.isfinite(value):
        raise ValueError("non-finite dot product")
    return max(-1.0, min(1.0, float(value)))


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [[float(value) for value in vector] for vector in raw]
    if not vectors or any(not vector for vector in vectors):
        raise ValueError("embedder returned empty vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent vector widths")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("embedder returned non-finite vectors")
    return vectors


def _cluster(action: str | None) -> str | None:
    return _ACTION_CLUSTER.get(action) if action else None


@dataclass(frozen=True)
class CompiledVectors:
    contract: CapabilityContract
    route_schema_vector: list[float]
    route_action_vector: list[float]
    capability_action_vector: list[float]
    object_vector: list[float]
    contract_vector: list[float]
    counterfactual_vectors: dict[str, list[float]]


@dataclass(frozen=True)
class GenericHead:
    model: Any
    threshold: float
    action_score_floor: float
    action_margin_floor: float
    calibration_positive_recall: float
    calibration_negative_fpr: float


def _synthetic_contract(
    action: str,
    resource: str,
    *,
    temporal_scope: str | None = None,
) -> CapabilityContract:
    operation_text = ACTION_PROTOTYPES[action]
    if temporal_scope is not None:
        operation_text += f"\ntemporal scope {temporal_scope}"
    object_text = f"generic resource: {resource}"
    contract_text = (
        "Registered tool capability.\n"
        f"Operation: {operation_text}\n"
        f"Resource and schema: {object_text}"
    )
    read_only = action not in {"create", "update", "delete", "send", "cancel", "execute"}
    return CapabilityContract(
        route_id="synthetic",
        tool_key="synthetic",
        endpoint_name="synthetic",
        adapter=None,
        operation_text=operation_text,
        object_text=object_text,
        data_contract_text="",
        contract_text=contract_text,
        input_fields=(),
        output_fields=(),
        declared_action=action,
        temporal_scope=temporal_scope,
        read_only=read_only,
        destructive=action == "delete",
        method=None,
    )


def _query_action(
    query_vector: list[float],
    action_vectors: dict[str, list[float]],
) -> tuple[str, float, float]:
    scored = sorted(
        (
            (family, _dot(query_vector, vector))
            for family, vector in action_vectors.items()
        ),
        key=lambda item: (-item[1], item[0]),
    )
    top_family, top_score = scored[0]
    second = scored[1][1] if len(scored) > 1 else -1.0
    return top_family, top_score, top_score - second


def _query_temporal(
    query_vector: list[float],
    temporal_vectors: dict[str, list[float]],
) -> tuple[str, float, float]:
    scored = sorted(
        (
            (family, _dot(query_vector, vector))
            for family, vector in temporal_vectors.items()
        ),
        key=lambda item: (-item[1], item[0]),
    )
    top_family, top_score = scored[0]
    second = scored[1][1] if len(scored) > 1 else -1.0
    return top_family, top_score, top_score - second


def _features(
    query_vector: list[float],
    compiled: CompiledVectors,
    *,
    action_vectors: dict[str, list[float]],
    temporal_vectors: dict[str, list[float]],
) -> tuple[list[float], dict[str, Any]]:
    contract = compiled.contract
    contract_score = _dot(query_vector, compiled.contract_vector)
    action_score = _dot(query_vector, compiled.capability_action_vector)
    object_score = _dot(query_vector, compiled.object_vector)

    counter_scores = {
        family: _dot(query_vector, vector)
        for family, vector in compiled.counterfactual_vectors.items()
    }
    best_counter_family, best_counter_score = max(
        counter_scores.items(),
        key=lambda item: (item[1], item[0]),
    )

    query_action, query_action_score, query_action_margin = _query_action(
        query_vector,
        action_vectors,
    )
    declared_cluster = _cluster(contract.declared_action)
    query_cluster = _cluster(query_action)
    exact_action_match = float(
        contract.declared_action is not None
        and query_action == contract.declared_action
    )
    cluster_match = float(
        declared_cluster is not None
        and query_cluster == declared_cluster
    )

    structural = structural_action_compatible(contract, query_action)
    structural_value = 0.0 if structural is None else (1.0 if structural else -1.0)

    query_temporal, query_temporal_score, query_temporal_margin = _query_temporal(
        query_vector,
        temporal_vectors,
    )
    temporal_known = contract.temporal_scope is not None
    temporal_match = float(
        temporal_known and query_temporal == contract.temporal_scope
    )

    values = [
        contract_score,
        action_score,
        object_score,
        best_counter_score,
        contract_score - best_counter_score,
        action_score - best_counter_score,
        exact_action_match,
        cluster_match,
        query_action_score,
        query_action_margin,
        structural_value,
        float(temporal_known),
        temporal_match,
        query_temporal_score,
        query_temporal_margin,
    ]
    details = {
        "contract_score": contract_score,
        "action_score": action_score,
        "object_score": object_score,
        "best_counterfactual_family": best_counter_family,
        "best_counterfactual_score": best_counter_score,
        "contract_counterfactual_margin": contract_score - best_counter_score,
        "query_action": query_action,
        "query_action_score": query_action_score,
        "query_action_margin": query_action_margin,
        "declared_action": contract.declared_action,
        "action_cluster_match": bool(cluster_match),
        "structural_compatibility": structural,
        "query_temporal": query_temporal,
        "query_temporal_score": query_temporal_score,
        "query_temporal_margin": query_temporal_margin,
        "declared_temporal": contract.temporal_scope,
        "temporal_match": bool(temporal_match),
    }
    return values, details


def _compile_vectors(
    contracts: Iterable[CapabilityContract],
    embedder: Embedder,
) -> dict[str, CompiledVectors]:
    contracts = list(contracts)
    texts: list[str] = []
    spans: list[tuple[CapabilityContract, int, int]] = []
    for contract in contracts:
        counterfactuals = counterfactual_action_texts(contract)
        start = len(texts)
        texts.extend(
            [
                contract.contract_text,
                contract.operation_text,
                contract.object_text,
                *counterfactuals.values(),
            ]
        )
        spans.append((contract, start, len(counterfactuals)))
    vectors = _to_vectors(embedder(texts))

    result: dict[str, CompiledVectors] = {}
    for contract, start, counter_count in spans:
        counterfactuals = counterfactual_action_texts(contract)
        counter_vectors = vectors[start + 3 : start + 3 + counter_count]
        result[contract.route_id] = CompiledVectors(
            contract=contract,
            route_schema_vector=vectors[start],
            route_action_vector=vectors[start + 1],
            capability_action_vector=vectors[start + 1],
            object_vector=vectors[start + 2],
            contract_vector=vectors[start],
            counterfactual_vectors=dict(
                zip(counterfactuals, counter_vectors, strict=True)
            ),
        )
    return result


def _generic_examples(resources: tuple[str, ...]) -> list[tuple[str, CapabilityContract, int]]:
    examples: list[tuple[str, CapabilityContract, int]] = []
    actions = tuple(ACTION_PROTOTYPES)
    languages = ("en", "ko", "es", "ja", "de", "mixed")

    for resource_index, resource in enumerate(resources):
        other_resource = resources[(resource_index + 1) % len(resources)]
        for action in actions:
            contract = _synthetic_contract(action, resource)
            for language in languages:
                query = _GENERIC_ACTION_PHRASES[action][language].format(r=resource)
                examples.append((query, contract, 1))

                # Deterministic same-resource hard negative.
                wrong_action = actions[(actions.index(action) + 3) % len(actions)]
                wrong_query = _GENERIC_ACTION_PHRASES[wrong_action][language].format(
                    r=resource
                )
                examples.append((wrong_query, contract, 0))

                # Correct operation against a different resource.
                object_mismatch = _GENERIC_ACTION_PHRASES[action][language].format(
                    r=other_resource
                )
                examples.append((object_mismatch, contract, 0))

        # Temporal counterfactuals use retrieval semantics so time scope becomes the
        # discriminating capability axis.
        for scope in ("current", "future", "historical"):
            temporal_contract = _synthetic_contract(
                "retrieve",
                resource,
                temporal_scope=scope,
            )
            for language in languages:
                positive = _TEMPORAL_PHRASES[scope][language].format(r=resource)
                examples.append((positive, temporal_contract, 1))
                wrong_scope = {
                    "current": "historical",
                    "historical": "future",
                    "future": "current",
                }[scope]
                negative = _TEMPORAL_PHRASES[wrong_scope][language].format(r=resource)
                examples.append((negative, temporal_contract, 0))

    # Generic OOD negatives are paired with several unrelated contracts.
    anchor_contracts = [
        _synthetic_contract(action, resources[index % len(resources)])
        for index, action in enumerate(actions[:6])
    ]
    for query in _OOD_QUERIES:
        for contract in anchor_contracts:
            examples.append((query, contract, 0))
    return examples


def _choose_threshold(
    probabilities: list[float],
    labels: list[int],
) -> tuple[float, float, float]:
    candidates = sorted({0.0, 1.0, *probabilities})
    best: tuple[float, float, float] | None = None
    for threshold in candidates:
        positives = [p >= threshold for p, y in zip(probabilities, labels, strict=True) if y]
        negatives = [p >= threshold for p, y in zip(probabilities, labels, strict=True) if not y]
        recall = sum(positives) / len(positives) if positives else 0.0
        fpr = sum(negatives) / len(negatives) if negatives else 0.0
        if recall >= 0.98 and fpr <= 0.005:
            candidate = (threshold, recall, fpr)
            if best is None or (recall, -fpr, -threshold) > (
                best[1],
                -best[2],
                -best[0],
            ):
                best = candidate
    if best is not None:
        return best

    # Fail closed when synthetic calibration cannot satisfy the preregistered internal
    # objective: choose the lowest-FPR point, then the highest recall.
    scored: list[tuple[float, float, float]] = []
    for threshold in candidates:
        positives = [p >= threshold for p, y in zip(probabilities, labels, strict=True) if y]
        negatives = [p >= threshold for p, y in zip(probabilities, labels, strict=True) if not y]
        recall = sum(positives) / len(positives) if positives else 0.0
        fpr = sum(negatives) / len(negatives) if negatives else 0.0
        scored.append((threshold, recall, fpr))
    scored.sort(key=lambda item: (item[2], -item[1], item[0]))
    return scored[0]


def fit_generic_head(embedder: Embedder) -> tuple[GenericHead, dict[str, Any]]:
    """Fit the route-identity-free verifier head on generic synthetic semantics."""

    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:  # pragma: no cover - research workflow installs sklearn.
        raise RuntimeError("scikit-learn is required for experiment #338") from exc

    action_names = list(ACTION_PROTOTYPES)
    temporal_names = list(TEMPORAL_PROTOTYPES)
    prototype_texts = [
        *(ACTION_PROTOTYPES[name] for name in action_names),
        *(TEMPORAL_PROTOTYPES[name] for name in temporal_names),
    ]
    prototype_vectors = _to_vectors(embedder(prototype_texts))
    action_vectors = dict(
        zip(action_names, prototype_vectors[: len(action_names)], strict=True)
    )
    temporal_vectors = dict(
        zip(temporal_names, prototype_vectors[len(action_names) :], strict=True)
    )

    def make_matrix(
        examples: list[tuple[str, CapabilityContract, int]],
    ) -> tuple[list[list[float]], list[int], list[dict[str, Any]]]:
        contracts_by_key = {
            (
                contract.declared_action,
                contract.object_text,
                contract.temporal_scope,
            ): contract
            for _, contract, _ in examples
        }
        unique_contracts: list[CapabilityContract] = []
        route_by_key: dict[tuple[str | None, str, str | None], str] = {}
        for key, contract in contracts_by_key.items():
            route_id = (
                f"synthetic::{contract.declared_action}::"
                f"{contract.object_text}::{contract.temporal_scope}"
            )
            route_by_key[key] = route_id
            unique_contracts.append(
                CapabilityContract(
                    route_id=route_id,
                    tool_key=contract.tool_key,
                    endpoint_name=contract.endpoint_name,
                    adapter=contract.adapter,
                    operation_text=contract.operation_text,
                    object_text=contract.object_text,
                    data_contract_text=contract.data_contract_text,
                    contract_text=contract.contract_text,
                    input_fields=contract.input_fields,
                    output_fields=contract.output_fields,
                    declared_action=contract.declared_action,
                    temporal_scope=contract.temporal_scope,
                    read_only=contract.read_only,
                    destructive=contract.destructive,
                    method=contract.method,
                )
            )
        compiled_by_route = _compile_vectors(unique_contracts, embedder)
        compiled_by_key = {
            key: compiled_by_route[route_id]
            for key, route_id in route_by_key.items()
        }

        query_vectors = _to_vectors(embedder([query for query, _, _ in examples]))
        matrix: list[list[float]] = []
        labels: list[int] = []
        details: list[dict[str, Any]] = []
        for query_vector, (_, contract, label) in zip(
            query_vectors,
            examples,
            strict=True,
        ):
            vector = compiled_by_key[
                (contract.declared_action, contract.object_text, contract.temporal_scope)
            ]
            features, row_details = _features(
                query_vector,
                vector,
                action_vectors=action_vectors,
                temporal_vectors=temporal_vectors,
            )
            matrix.append(features)
            labels.append(label)
            details.append(row_details)
        return matrix, labels, details

    fit_examples = _generic_examples(_FIT_RESOURCES)
    fit_x, fit_y, _ = make_matrix(fit_examples)
    model = LogisticRegression(
        random_state=HEAD_RANDOM_STATE,
        max_iter=2000,
        class_weight="balanced",
        C=1.0,
    )
    model.fit(fit_x, fit_y)

    calibration_examples = _generic_examples(_CALIBRATION_RESOURCES)
    cal_x, cal_y, cal_details = make_matrix(calibration_examples)
    probabilities = [
        float(value)
        for value in model.predict_proba(cal_x)[:, 1]
    ]
    threshold, recall, fpr = _choose_threshold(probabilities, cal_y)

    positive_action_scores = [
        float(detail["query_action_score"])
        for detail, label in zip(cal_details, cal_y, strict=True)
        if label == 1
    ]
    positive_action_margins = [
        float(detail["query_action_margin"])
        for detail, label in zip(cal_details, cal_y, strict=True)
        if label == 1
    ]
    action_score_floor = min(positive_action_scores) if positive_action_scores else 1.0
    action_margin_floor = min(positive_action_margins) if positive_action_margins else 1.0

    return (
        GenericHead(
            model=model,
            threshold=threshold,
            action_score_floor=action_score_floor,
            action_margin_floor=action_margin_floor,
            calibration_positive_recall=recall,
            calibration_negative_fpr=fpr,
        ),
        {
            "action_names": action_names,
            "temporal_names": temporal_names,
            "action_vectors": action_vectors,
            "temporal_vectors": temporal_vectors,
        },
    )


def _raw_schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [
        route_id,
        tool.description.strip(),
        endpoint.description.strip(),
    ]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _raw_action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    aliases = list(endpoint.operation_aliases)
    descriptive_fallback = endpoint.description.strip() if not aliases else ""
    return "\n".join(
        dict.fromkeys(
            part
            for part in [operation_name, *aliases, descriptive_fallback]
            if part
        )
    )


class RegistryCapabilityVerifier:
    """Raw BGE top-1 route authority plus a generic learned veto gate."""

    def __init__(
        self,
        registry: Any,
        embedder: Embedder,
        *,
        generic_state: tuple[GenericHead, dict[str, Any]] | None = None,
    ) -> None:
        self.registry = registry
        self.embedder = embedder
        self.contracts = compile_registry(registry)
        if not self.contracts:
            raise ValueError("registry must contain at least one endpoint")

        self.head, prototype_bundle = (
            generic_state if generic_state is not None else fit_generic_head(embedder)
        )
        self.action_vectors = prototype_bundle["action_vectors"]
        self.temporal_vectors = prototype_bundle["temporal_vectors"]

        contract_vectors = _compile_vectors(self.contracts, embedder)
        raw_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                raw_specs[route_id] = (
                    _raw_schema_text(tool, endpoint),
                    _raw_action_text(endpoint),
                )
        route_ids = sorted(raw_specs)
        raw_texts = [
            *(raw_specs[route_id][0] for route_id in route_ids),
            *(raw_specs[route_id][1] for route_id in route_ids),
        ]
        raw_vectors = _to_vectors(embedder(raw_texts))
        split = len(route_ids)
        raw_schema_vectors = dict(
            zip(route_ids, raw_vectors[:split], strict=True)
        )
        raw_action_vectors = dict(
            zip(route_ids, raw_vectors[split:], strict=True)
        )
        for route_id in route_ids:
            current = contract_vectors[route_id]
            contract_vectors[route_id] = CompiledVectors(
                contract=current.contract,
                route_schema_vector=raw_schema_vectors[route_id],
                route_action_vector=raw_action_vectors[route_id],
                capability_action_vector=current.capability_action_vector,
                object_vector=current.object_vector,
                contract_vector=current.contract_vector,
                counterfactual_vectors=current.counterfactual_vectors,
            )
        self.compiled = contract_vectors
        self.route_ids = tuple(route_ids)

    def score(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        ranked: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            compiled = self.compiled[route_id]
            schema_score = _dot(query_vector, compiled.route_schema_vector)
            action_score = _dot(query_vector, compiled.route_action_vector)
            fused = SCHEMA_WEIGHT * schema_score + ACTION_WEIGHT * action_score
            ranked.append((route_id, fused))
        ranked.sort(key=lambda item: (-item[1], item[0]))
        top_route, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else None

        compiled = self.compiled[top_route]
        features, details = _features(
            query_vector,
            compiled,
            action_vectors=self.action_vectors,
            temporal_vectors=self.temporal_vectors,
        )
        probability = float(self.head.model.predict_proba([features])[0][1])

        # Deterministic structural veto only when the generic operation parser is at least
        # as confident as every positive synthetic calibration example.
        structural = details["structural_compatibility"]
        confident_action = (
            float(details["query_action_score"]) >= self.head.action_score_floor
            and float(details["query_action_margin"]) >= self.head.action_margin_floor
        )
        hard_veto = bool(structural is False and confident_action)
        accepted = probability >= self.head.threshold and not hard_veto

        return {
            "top_route": top_route,
            "top_score": top_score,
            "second_score": second_score,
            "top_margin": (
                top_score - second_score if second_score is not None else 2.0
            ),
            "accepted": accepted,
            "verifier_probability": probability,
            "verifier_threshold": self.head.threshold,
            "hard_structural_veto": hard_veto,
            "features": features,
            "details": details,
            "ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in ranked
            ],
        }
