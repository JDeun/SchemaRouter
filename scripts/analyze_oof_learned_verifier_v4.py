"""Grouped OOF learned winner-verifier diagnostic for operation routing."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmark_decision_routing import reference_registry  # noqa: E402
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    MODEL_NAME,
    MODEL_REVISION,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
    _cosine,
)

RANDOM_STATE = 20260928
EXPECTED_LANGUAGES = ("de", "en", "es", "ja", "ko", "mixed")
CLASSIFIER_NAMES = ("logistic", "hgb")
ACCEPTANCE_THRESHOLDS = (
    0.50,
    0.60,
    0.70,
    0.80,
    0.85,
    0.90,
    0.925,
    0.95,
    0.97,
    0.98,
    0.99,
    0.995,
)
CONTINUOUS_FEATURES = (
    "raw_top_score",
    "raw_top_margin",
    "raw_top_schema_score",
    "raw_top_action_score",
    "schema_action_abs_delta",
    "raw_positive_score",
    "best_local_positive_score",
    "best_local_negative_score",
    "negative_minus_raw_positive",
    "negative_minus_best_positive",
    "negative_outrank_count",
    "winner_domain_anchor_score",
    "best_known_domain_score",
    "best_background_score",
    "background_minus_best_known",
    "background_minus_winner_domain",
    "schema_top_agrees_raw",
    "action_top_agrees_raw",
    "schema_action_top_agree",
)
CATEGORICAL_FEATURES = ("raw_top_route",)

DOMAIN_ANCHORS: dict[str, str] = {
    "weather": "weather and meteorological information",
    "materials": "materials science and crystal structure information",
    "papers": "academic papers and citation information",
    "finance": "market quotes and historical price information",
    "calendar": "calendar events and schedules",
    "support": "customer support tickets",
    "inventory": "inventory items and stock management",
    "users": "user accounts and profiles",
}

NEGATIVE_CAPABILITY_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "weather": (
        "satellite cloud imagery",
        "aviation METAR and TAF reports",
        "live lightning strike maps",
        "pollen and allergy outlooks",
    ),
    "materials": (
        "XRD pattern simulation",
        "defect formation energy calculation",
        "laboratory synthesis recipe design",
        "molecular dynamics simulation",
    ),
    "papers": (
        "full paper translation",
        "citation network visualization",
        "plagiarism detection",
        "emailing corresponding authors",
    ),
    "finance": (
        "securities trading and selling shares",
        "portfolio rebalancing",
        "live options chains",
        "capital gains tax reporting",
    ),
    "calendar": (
        "declining calendar invitations",
        "setting event reminders",
        "sharing calendars",
        "booking rooms or resources",
    ),
    "support": (
        "reopening support tickets",
        "changing ticket priority",
        "deleting support tickets",
        "escalating tickets to another support tier",
    ),
    "inventory": (
        "printing inventory barcode labels",
        "changing retail prices",
        "creating catalog items",
        "exporting inventory to CSV",
    ),
    "users": (
        "assigning user roles or permissions",
        "suspending user accounts",
        "verifying email addresses",
        "listing active login sessions",
    ),
}

BACKGROUND_PROTOTYPES: tuple[str, ...] = (
    "sports scores, team standings, and game results",
    "travel itineraries, flights, hotels, and tourist attractions",
    "restaurants, recipes, cooking, and food recommendations",
    "medical symptoms, diagnosis, treatment, and medications",
    "legal advice, laws, contracts, and court procedures",
    "software programming, debugging, and source code",
    "translation, grammar, and language learning",
    "music, movies, games, and entertainment recommendations",
    "shopping, consumer products, prices, and product reviews",
    "news, politics, elections, and current events",
    "maps, locations, driving directions, and navigation",
    "email, messaging, and social media communication",
    "image generation, photography, and visual design",
    "mathematics, calculations, and homework",
    "personal productivity, notes, and document writing",
    "general knowledge, trivia, and casual conversation",
)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p05": _quantile(values, 0.05),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _load_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
    )


def _embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def _tool(route: str | None) -> str | None:
    if not isinstance(route, str) or "." not in route:
        return None
    return route.split(".", 1)[0]


def _positive_capability_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    parts = [
        operation_name,
        *endpoint.operation_aliases,
        endpoint.description.strip(),
    ]
    return "\n".join(dict.fromkeys(part for part in parts if part))


def _target(expected: str | None, raw_top_route: str) -> int:
    return int(expected is not None and raw_top_route == expected)


def _typed_state(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "match"
    if probability <= 1.0 - threshold:
        return "no_match"
    return "unknown"


def _feature_vector(row: dict[str, Any]) -> list[Any]:
    values = [float(row["features"][name]) for name in CONTINUOUS_FEATURES]
    return [*values, str(row["raw_top_route"])]


def _build_classifier(name: str):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric_indexes = list(range(len(CONTINUOUS_FEATURES)))
    route_index = [len(CONTINUOUS_FEATURES)]
    preprocess = ColumnTransformer(
        [
            ("continuous", StandardScaler(), numeric_indexes),
            (
                "route",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                route_index,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    if name == "logistic":
        classifier = LogisticRegression(
            C=1.0,
            penalty="l2",
            solver="lbfgs",
            max_iter=2000,
            random_state=RANDOM_STATE,
        )
    elif name == "hgb":
        classifier = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=150,
            max_leaf_nodes=7,
            min_samples_leaf=20,
            l2_regularization=5.0,
            random_state=RANDOM_STATE,
        )
    else:
        raise ValueError(f"unknown classifier: {name}")
    return Pipeline(
        [
            ("preprocess", preprocess),
            ("classifier", classifier),
        ]
    )


def _extract_rows(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = reference_registry()
    model_started = time.perf_counter_ns()
    model = _load_model()
    model_load_ms = (time.perf_counter_ns() - model_started) / 1_000_000
    embed = _embedder(model)

    route_started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(registry, embed)
    route_static_ms = (time.perf_counter_ns() - route_started) / 1_000_000

    domains = sorted(DOMAIN_ANCHORS)
    positive_items: list[tuple[str, str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            positive_items.append(
                (
                    tool.key,
                    f"{tool.key}.{endpoint.name}",
                    _positive_capability_text(endpoint),
                )
            )
    positive_items.sort(key=lambda item: item[1])
    negative_items = [
        (domain, prototype)
        for domain in domains
        for prototype in NEGATIVE_CAPABILITY_PROTOTYPES[domain]
    ]

    static_started = time.perf_counter_ns()
    static_vectors = embed(
        [text for _, _, text in positive_items]
        + [prototype for _, prototype in negative_items]
        + [DOMAIN_ANCHORS[domain] for domain in domains]
        + list(BACKGROUND_PROTOTYPES)
    )
    evidence_static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    positive_end = len(positive_items)
    negative_end = positive_end + len(negative_items)
    domain_end = negative_end + len(domains)

    positive_vectors: dict[str, list[tuple[str, list[float]]]] = {
        domain: [] for domain in domains
    }
    positive_by_route: dict[str, list[float]] = {}
    for (domain, route_id, _), vector in zip(
        positive_items,
        static_vectors[:positive_end],
        strict=True,
    ):
        positive_vectors[domain].append((route_id, vector))
        positive_by_route[route_id] = vector

    negative_vectors: dict[str, list[tuple[str, list[float]]]] = {
        domain: [] for domain in domains
    }
    for (domain, prototype), vector in zip(
        negative_items,
        static_vectors[positive_end:negative_end],
        strict=True,
    ):
        negative_vectors[domain].append((prototype, vector))

    domain_vectors = dict(
        zip(
            domains,
            static_vectors[negative_end:domain_end],
            strict=True,
        )
    )
    background_vectors = list(
        zip(
            BACKGROUND_PROTOTYPES,
            static_vectors[domain_end:],
            strict=True,
        )
    )

    route_ids = list(backend.route_ids)
    allowed_routes = set(route_ids)
    rows: list[dict[str, Any]] = []
    feature_latencies: list[float] = []

    for case in cases:
        started = time.perf_counter_ns()
        query_vector = embed([str(case["query"])])[0]

        route_scores: list[tuple[str, float, float, float]] = []
        for route_id in route_ids:
            schema_score = _cosine(
                query_vector,
                backend._schema_vectors[route_id],  # noqa: SLF001
            )
            action_score = _cosine(
                query_vector,
                backend._action_vectors[route_id],  # noqa: SLF001
            )
            fused_score = (
                SCHEMA_WEIGHT * schema_score
                + ACTION_WEIGHT * action_score
            )
            route_scores.append(
                (route_id, fused_score, schema_score, action_score)
            )
        route_scores.sort(key=lambda item: (-item[1], item[0]))
        raw_route, raw_score, raw_schema, raw_action = route_scores[0]
        second_score = route_scores[1][1] if len(route_scores) > 1 else -1.0
        raw_margin = raw_score - second_score
        schema_top = min(route_scores, key=lambda item: (-item[2], item[0]))[0]
        action_top = min(route_scores, key=lambda item: (-item[3], item[0]))[0]

        winner_domain = _tool(raw_route)
        if winner_domain is None or winner_domain not in domain_vectors:
            raise RuntimeError(f"unknown winner domain: {raw_route}")

        raw_positive_score = _cosine(
            query_vector,
            positive_by_route[raw_route],
        )
        local_positive_scores = [
            _cosine(query_vector, vector)
            for _, vector in positive_vectors[winner_domain]
        ]
        local_negative_scores = [
            _cosine(query_vector, vector)
            for _, vector in negative_vectors[winner_domain]
        ]
        best_positive = max(local_positive_scores)
        best_negative = max(local_negative_scores)
        negative_outrank_count = sum(
            score > raw_positive_score for score in local_negative_scores
        )

        known_scores = {
            domain: _cosine(query_vector, vector)
            for domain, vector in domain_vectors.items()
        }
        best_known = max(known_scores.values())
        winner_domain_score = known_scores[winner_domain]
        best_background = max(
            _cosine(query_vector, vector)
            for _, vector in background_vectors
        )

        features = {
            "raw_top_score": raw_score,
            "raw_top_margin": raw_margin,
            "raw_top_schema_score": raw_schema,
            "raw_top_action_score": raw_action,
            "schema_action_abs_delta": abs(raw_schema - raw_action),
            "raw_positive_score": raw_positive_score,
            "best_local_positive_score": best_positive,
            "best_local_negative_score": best_negative,
            "negative_minus_raw_positive": (
                best_negative - raw_positive_score
            ),
            "negative_minus_best_positive": (
                best_negative - best_positive
            ),
            "negative_outrank_count": float(negative_outrank_count),
            "winner_domain_anchor_score": winner_domain_score,
            "best_known_domain_score": best_known,
            "best_background_score": best_background,
            "background_minus_best_known": best_background - best_known,
            "background_minus_winner_domain": (
                best_background - winner_domain_score
            ),
            "schema_top_agrees_raw": float(schema_top == raw_route),
            "action_top_agrees_raw": float(action_top == raw_route),
            "schema_action_top_agree": float(schema_top == action_top),
        }
        feature_latency_ms = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        feature_latencies.append(feature_latency_ms)
        expected = case.get("expected")
        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "raw_top_route": raw_route,
                "raw_correct": expected is not None and raw_route == expected,
                "verifier_target": _target(expected, raw_route),
                "features": features,
                "feature_latency_ms": feature_latency_ms,
                "authority_violation": raw_route not in allowed_routes,
            }
        )

    return rows, {
        "model_load_ms": model_load_ms,
        "route_static_init_ms": route_static_ms,
        "evidence_static_init_ms": evidence_static_ms,
        "feature_extraction_latency_ms": _distribution(feature_latencies),
    }


def _oof_predict(
    rows: list[dict[str, Any]],
    classifier_name: str,
) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    languages = sorted({str(row["language"]) for row in rows})
    if tuple(languages) != EXPECTED_LANGUAGES:
        raise ValueError(
            f"unexpected language groups: {languages!r}"
        )

    x = np.asarray([_feature_vector(row) for row in rows], dtype=object)
    y = np.asarray([int(row["verifier_target"]) for row in rows], dtype=int)
    probs = np.full(len(rows), np.nan, dtype=float)
    prediction_latencies = np.full(len(rows), np.nan, dtype=float)
    folds: list[dict[str, Any]] = []

    for held_language in EXPECTED_LANGUAGES:
        train_idx = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if row["language"] != held_language
            ],
            dtype=int,
        )
        test_idx = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if row["language"] == held_language
            ],
            dtype=int,
        )
        model = _build_classifier(classifier_name)
        fit_started = time.perf_counter_ns()
        model.fit(x[train_idx], y[train_idx])
        fit_ms = (time.perf_counter_ns() - fit_started) / 1_000_000
        class_index = list(
            model.named_steps["classifier"].classes_
        ).index(1)

        for index in test_idx:
            started = time.perf_counter_ns()
            probability = float(
                model.predict_proba(x[index : index + 1])[0][class_index]
            )
            prediction_latencies[index] = (
                time.perf_counter_ns() - started
            ) / 1_000_000
            probs[index] = probability

        diagnostics: dict[str, Any] = {
            "held_language": held_language,
            "train_cases": int(len(train_idx)),
            "test_cases": int(len(test_idx)),
            "train_match": int(y[train_idx].sum()),
            "test_match": int(y[test_idx].sum()),
            "fit_ms": fit_ms,
            "roc_auc": float(roc_auc_score(y[test_idx], probs[test_idx])),
            "average_precision": float(
                average_precision_score(y[test_idx], probs[test_idx])
            ),
        }
        if classifier_name == "logistic":
            preprocess = model.named_steps["preprocess"]
            classifier = model.named_steps["classifier"]
            names = list(preprocess.get_feature_names_out())
            coefs = [float(value) for value in classifier.coef_[0]]
            ranked = sorted(
                zip(names, coefs, strict=True),
                key=lambda item: (-abs(item[1]), item[0]),
            )
            diagnostics["top_absolute_coefficients"] = [
                {"feature": feature, "coefficient": coefficient}
                for feature, coefficient in ranked[:20]
            ]
        folds.append(diagnostics)

    if bool(np.isnan(probs).any()):
        raise RuntimeError("OOF prediction vector contains missing values")
    if bool(np.isnan(prediction_latencies).any()):
        raise RuntimeError("OOF latency vector contains missing values")

    return {
        "probabilities": [float(value) for value in probs],
        "prediction_latencies_ms": [
            float(value) for value in prediction_latencies
        ],
        "roc_auc": float(roc_auc_score(y, probs)),
        "average_precision": float(average_precision_score(y, probs)),
        "folds": folds,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _evaluate_threshold(
    rows: list[dict[str, Any]],
    probabilities: list[float],
    prediction_latencies: list[float],
    *,
    classifier_name: str,
    threshold: float,
) -> dict[str, Any]:
    states = [
        _typed_state(probability, threshold)
        for probability in probabilities
    ]
    accepted = [state == "match" for state in states]

    supported_indexes = [
        index for index, row in enumerate(rows)
        if row["expected"] is not None
    ]
    near_indexes = [
        index for index, row in enumerate(rows)
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood_indexes = [
        index for index, row in enumerate(rows)
        if row["category"] == "out_of_domain"
    ]
    unsupported_indexes = [
        index for index, row in enumerate(rows)
        if row["expected"] is None
    ]

    supported_correct = sum(
        accepted[index] and bool(rows[index]["raw_correct"])
        for index in supported_indexes
    )
    wrong_supported_accepted = sum(
        accepted[index] and not bool(rows[index]["raw_correct"])
        for index in supported_indexes
    )
    near_rejected = sum(not accepted[index] for index in near_indexes)
    ood_rejected = sum(not accepted[index] for index in ood_indexes)
    false_routes = sum(accepted[index] for index in unsupported_indexes)

    supported_exact = _safe_rate(
        supported_correct,
        len(supported_indexes),
    )
    near_rejection = _safe_rate(near_rejected, len(near_indexes))
    ood_rejection = _safe_rate(ood_rejected, len(ood_indexes))
    false_rate = _safe_rate(false_routes, len(unsupported_indexes))

    combined_latencies = [
        float(row["feature_latency_ms"]) + float(prediction_latencies[index])
        for index, row in enumerate(rows)
    ]
    combined_latency = _distribution(combined_latencies)
    p95 = combined_latency["p95"]

    per_language: dict[str, Any] = {}
    for language in EXPECTED_LANGUAGES:
        indexes = [
            index for index, row in enumerate(rows)
            if row["language"] == language
        ]
        supported = [
            index for index in indexes
            if rows[index]["expected"] is not None
        ]
        unsupported = [
            index for index in indexes
            if rows[index]["expected"] is None
        ]
        per_language[language] = {
            "cases": len(indexes),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted[index]
                    and bool(rows[index]["raw_correct"])
                    for index in supported
                ),
                len(supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not accepted[index] for index in unsupported),
                len(unsupported),
            ),
            "false_routes": sum(
                accepted[index] for index in unsupported
            ),
        }

    per_route: dict[str, Any] = {}
    routes = sorted({str(row["raw_top_route"]) for row in rows})
    for route in routes:
        indexes = [
            index for index, row in enumerate(rows)
            if row["raw_top_route"] == route
        ]
        per_route[route] = {
            "cases": len(indexes),
            "accepted": sum(accepted[index] for index in indexes),
            "accepted_correct": sum(
                accepted[index] and bool(rows[index]["raw_correct"])
                for index in indexes
            ),
        }

    per_family: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in rows
            if row["unsupported_family"] is not None
        }
    )
    for family in families:
        indexes = [
            index for index, row in enumerate(rows)
            if row["unsupported_family"] == family
        ]
        per_family[family] = {
            "cases": len(indexes),
            "rejected": sum(not accepted[index] for index in indexes),
            "rejection_rate": _safe_rate(
                sum(not accepted[index] for index in indexes),
                len(indexes),
            ),
        }

    state_counts = {
        state: states.count(state)
        for state in ("match", "no_match", "unknown")
    }
    quality_gate_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_rate <= 0.01
        and p95 is not None
        and float(p95) <= 250.0
    )

    return {
        "rule_id": f"{classifier_name}-p{threshold:.3f}",
        "classifier": classifier_name,
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_exact,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejection,
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_rate,
        "typed_state_counts": state_counts,
        "per_language": per_language,
        "per_route": per_route,
        "unsupported_family_rejection": per_family,
        "combined_latency_ms": combined_latency,
        "quality_gate_pass": quality_gate_pass,
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows, extraction = _extract_rows(cases)
    authority_violations = sum(
        bool(row["authority_violation"]) for row in rows
    )
    languages = sorted({str(row["language"]) for row in rows})
    if tuple(languages) != EXPECTED_LANGUAGES:
        raise ValueError(f"unexpected languages: {languages!r}")

    classifier_results: dict[str, Any] = {}
    rules: list[dict[str, Any]] = []
    for classifier_name in CLASSIFIER_NAMES:
        oof = _oof_predict(rows, classifier_name)
        classifier_results[classifier_name] = {
            "roc_auc": oof["roc_auc"],
            "average_precision": oof["average_precision"],
            "prediction_latency_ms": _distribution(
                oof["prediction_latencies_ms"]
            ),
            "folds": oof["folds"],
        }
        for threshold in ACCEPTANCE_THRESHOLDS:
            rules.append(
                _evaluate_threshold(
                    rows,
                    oof["probabilities"],
                    oof["prediction_latencies_ms"],
                    classifier_name=classifier_name,
                    threshold=threshold,
                )
            )
        for row, probability in zip(
            rows,
            oof["probabilities"],
            strict=True,
        ):
            row[f"{classifier_name}_oof_p_match"] = probability

    model_order = {"logistic": 0, "hgb": 1}
    candidate_worthy = [
        rule
        for rule in rules
        if bool(rule["quality_gate_pass"])
        and authority_violations == 0
    ]
    candidate_worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            -float(rule["out_of_domain_rejection"]),
            model_order[str(rule["classifier"])],
            float(rule["threshold"]),
        )
    )

    target_match = sum(int(row["verifier_target"]) for row in rows)
    supported = sum(row["expected"] is not None for row in rows)
    near = sum(
        row["category"] == "near_domain_unsupported_operation"
        for row in rows
    )
    ood = sum(row["category"] == "out_of_domain" for row in rows)

    artifact_rows = [
        {
            "case_id": row["case_id"],
            "category": row["category"],
            "language": row["language"],
            "unsupported_family": row["unsupported_family"],
            "expected": row["expected"],
            "raw_top_route": row["raw_top_route"],
            "raw_correct": row["raw_correct"],
            "verifier_target": row["verifier_target"],
            "features": row["features"],
            "feature_latency_ms": row["feature_latency_ms"],
            "logistic_oof_p_match": row["logistic_oof_p_match"],
            "hgb_oof_p_match": row["hgb_oof_p_match"],
        }
        for row in rows
    ]

    return {
        "experiment": "grouped-oof-learned-winner-verifier-v1",
        "model": {
            "embedding": MODEL_NAME,
            "revision": MODEL_REVISION,
            "schema_weight": SCHEMA_WEIGHT,
            "action_weight": ACTION_WEIGHT,
        },
        "feature_schema": {
            "continuous": list(CONTINUOUS_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
            "language_is_feature": False,
            "query_text_is_feature": False,
            "label_fields_are_features": False,
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": supported,
            "near_domain_cases": near,
            "ood_cases": ood,
            "verifier_match_targets": target_match,
            "verifier_no_match_targets": len(rows) - target_match,
            "raw_supported_top1_accuracy": _safe_rate(
                target_match,
                supported,
            ),
            "authority_violations": authority_violations,
            "execution_errors": 0,
            **extraction,
            "fixed_rule_count": len(rules),
            "candidate_worthy_rule_count": len(candidate_worthy),
            "best_candidate": (
                candidate_worthy[0] if candidate_worthy else None
            ),
        },
        "classifiers": classifier_results,
        "candidate_worthy_rules": candidate_worthy,
        "rule_results": rules,
        "rows": artifact_rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "oof_group": "language",
            "failed_fresh_confirmation_used_for_tuning": False,
            "calibration_or_blind_used": False,
            "query_text_used_as_classifier_feature": False,
            "language_used_as_classifier_feature": False,
            "labels_used_as_classifier_features": False,
            "verifier_can_select_route": False,
            "veto_only": True,
            "no_pseudo_route": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_top1_accuracy": result["summary"][
                    "raw_supported_top1_accuracy"
                ],
                "fixed_rule_count": result["summary"]["fixed_rule_count"],
                "candidate_worthy_rule_count": result["summary"][
                    "candidate_worthy_rule_count"
                ],
                "best_candidate": result["summary"]["best_candidate"],
                "classifiers": {
                    name: {
                        "roc_auc": diagnostics["roc_auc"],
                        "average_precision": diagnostics[
                            "average_precision"
                        ],
                        "prediction_latency_ms": diagnostics[
                            "prediction_latency_ms"
                        ],
                    }
                    for name, diagnostics in result["classifiers"].items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
