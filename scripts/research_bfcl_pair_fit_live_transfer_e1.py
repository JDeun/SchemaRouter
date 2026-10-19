"""Prospective PUBLIC BFCL sibling-category pair-fit vs E5 no-fit (DEV/E1).

Train on publisher BFCL V4 multiple/irrelevance, calibrate on disjoint IDs,
evaluate *other* original live_relevance/live_irrelevance publisher categories.
All examples are PUBLIC; no live tool call, native E2 or default change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from schemarouter import E5CachedEmbedder, EmbeddingDecisionBackend
from scripts.research_bfcl_v4_public_relevance_e1 import (
    BFCL_COMMIT,
    MODEL_ID,
    MODEL_REVISION,
    ROOT,
    _source_text,
    _words,
    fetch_original_data,
)

LIVE_BLOBS = {
    "live_relevance": ("BFCL_v4_live_relevance.json",
                       "1b0190995f4554b980da2dd7ab15195f4e047e62"),
    "live_irrelevance": ("BFCL_v4_live_irrelevance.json",
                         "547f60220b546ea5c864815dbb310b2f46ec0f43"),
}
TARGET_CALIBRATION_FPR = 0.10
MAX_ORIGINAL_BYTES = 3_000_000
MAX_LIVE_CASES = 5_000
MAX_FUNCTIONS = 500


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
    ).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("BFCL repeated source JSON field")
        out[k] = v
    return out


def _reject_nonfinite(_: str) -> None:
    raise ValueError("BFCL nonfinite JSON value")


def load_live_source() -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    cohorts: dict[str, list[dict[str, Any]]] = {}
    source_shas: dict[str, str] = {}
    for kind, (path, expected) in LIVE_BLOBS.items():
        with urllib.request.urlopen(ROOT + path, timeout=90) as stream:
            raw = stream.read(MAX_ORIGINAL_BYTES + 1)
        if len(raw) > MAX_ORIGINAL_BYTES or git_blob(raw) != expected:
            raise ValueError("publisher BFCL live source original hash mismatch")
        records = [
            json.loads(
                line, object_pairs_hook=_reject_duplicate_pairs,
                parse_constant=_reject_nonfinite,
            )
            for line in raw.decode("utf-8").splitlines() if line.strip()
        ]
        if (
            not 10 <= len(records) <= MAX_LIVE_CASES
            or len({row.get("id") for row in records}) != len(records)
            or any(not row["id"].startswith(kind + "_") for row in records)
        ):
            raise ValueError("BFCL live category or identifiers invalid")
        cohorts[kind] = records
        source_shas[kind] = hashlib.sha256(raw).hexdigest()
    if len(cohorts["live_relevance"]) != 16:
        raise ValueError("BFCL original publisher 16 live relevance IDs drifted")
    return cohorts, source_shas


def parse_task(row: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    turns = row.get("question")
    funcs = row.get("function")
    if (
        type(turns) is not list or len(turns) != 1
        or type(turns[0]) is not list
        or not 1 <= len(turns[0]) <= 16
        or any(type(message) is not dict for message in turns[0])
        or turns[0][-1].get("role") != "user"
        or any(
            message.get("role") not in ("system", "assistant", "user")
            for message in turns[0][:-1]
        )
        or type(funcs) is not list
        or not 0 <= len(funcs) <= MAX_FUNCTIONS
        or any(
            type(fn) is not dict
            or type(fn.get("name")) is not str
            or type(fn.get("description")) is not str
            for fn in funcs
        )
    ):
        # Only public structure counts/types enter diagnostics. Never echo
        # prompt, system text, tool name or sensitive source payload.
        outer = len(turns) if type(turns) is list else -1
        messages = len(turns[0]) if (
            type(turns) is list and turns and type(turns[0]) is list
        ) else -1
        menu = len(funcs) if type(funcs) is list else -1
        raise ValueError(
            f"BFCL source shape unsupported (outer={outer}, "
            f"messages={messages}, offered={menu})"
        )
    # The last user message is evaluated. All preceding corpus messages
    # remain untrusted context and are deliberately NOT treated as host
    # system instructions, authority, or model-relevance feature inputs.
    user = turns[0][-1].get("content")
    if type(user) is not str or not user.strip() or len(user) > 25_000:
        raise ValueError("BFCL user query invalid")
    if len({fn["name"] for fn in funcs}) != len(funcs):
        raise ValueError("duplicate publisher offered function name")
    return user, funcs


def pair_features(
    query: str, offered: list[dict[str, Any]], embedder: E5CachedEmbedder,
) -> list[list[float]]:
    if not offered:
        raise ValueError("pair similarity cannot score an empty source menu")
    texts = [_source_text(fn) for fn in offered]
    if any(not text.strip() or len(text) > 12_000 for text in texts):
        raise ValueError("BFCL function semantic text out of bounds")
    query_vec, *passage_vecs = embedder([query, *texts])
    tokens = _words(query)
    features = []
    for passage, vec in zip(texts, passage_vecs, strict=True):
        p = _words(passage)
        intersection = len(tokens & p)
        # No number-of-offered-functions feature: training categories have
        # systematically different menu sizes. This is individual fit data.
        cosine = EmbeddingDecisionBackend._cosine(query_vec, vec)
        features.append([
            cosine,
            intersection / max(1, len(tokens | p)),
            min(5, intersection) / 5,
        ])
    return features


def fit_scores(
    features: list[list[float]], model: Any,
) -> list[float]:
    values = model.predict_proba(features)
    return [float(row[1]) for row in values]


def fixed_fpr_cutoff(negatives: list[float]) -> float:
    if (
        len(negatives) != 120
        or any(type(z) is not float or not math.isfinite(z) for z in negatives)
    ):
        raise ValueError("exact 120 publisher calibration negatives required")
    # Strict > the 13th highest negative achieves <=12/120 calibration FPR,
    # without ever inspecting live evaluation labels or choosing live cutoffs.
    return math.nextafter(sorted(negatives, reverse=True)[12], math.inf)


def familywise_negative_tail_accept(
    candidate_scores: list[float],
    negative_calibration_scores: list[float],
    *,
    alpha: float = 0.10,
) -> bool:
    """Conservative original-public negative tail for a menu of functions.

    Uses a single raw per-function empirical p-value per offered candidate,
    and the Bonferroni alpha/menu bound. Its finite 120-negative resolution
    automatically abstains on too-large menus instead of extrapolating.
    The publisher categories are PUBLIC and already exposed, so this
    diagnostic is NOT a production-calibrated error guarantee or E2.
    """
    if (
        type(candidate_scores) is not list or not 1 <= len(candidate_scores) <= 500
        or type(negative_calibration_scores) is not list
        or len(negative_calibration_scores) != 120
        or type(alpha) is not float or alpha != 0.10
        or any(type(z) is not float or not math.isfinite(z)
               for z in [*candidate_scores, *negative_calibration_scores])
    ):
        raise ValueError("invalid source-pinned menu-wise negative calibration")
    highest = max(candidate_scores)
    # Add-one empirical p-value with ties counted as equally negative.
    extreme = sum(z >= highest for z in negative_calibration_scores)
    p_value = (extreme + 1) / (len(negative_calibration_scores) + 1)
    return len(candidate_scores) * p_value <= alpha


def stats(positive: list[float], negative: list[float], cutoff: float) -> dict[str, Any]:
    if (
        not positive or not negative or not math.isfinite(cutoff)
        or any(not math.isfinite(x) for x in [*positive, *negative])
    ):
        raise ValueError("nonempty finite fit/no-fit evidence required")
    return {
        "supported_total": len(positive),
        "supported_admitted": sum(x >= cutoff for x in positive),
        "supported_false_refused": sum(x < cutoff for x in positive),
        "unsupported_total": len(negative),
        "unsupported_false_accepted": sum(x >= cutoff for x in negative),
        "unsupported_correctly_refused": sum(x < cutoff for x in negative),
    }


def run(
    training: dict[str, list[dict[str, Any]]],
    live: dict[str, list[dict[str, Any]]],
    encode: Any,
    *,
    menu_familywise: bool = False,
) -> dict[str, Any]:
    if type(menu_familywise) is not bool:
        raise ValueError("explicit BFCL E1 family-wise mode must be boolean")
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    gold = {}
    for row in training["gold"]:
        gt = row["ground_truth"]
        if type(gt) is not list or len(gt) != 1 or type(gt[0]) is not dict or len(gt[0]) != 1:
            raise ValueError("unsupported publisher exact-one gold")
        gold[row["id"]] = next(iter(gt[0]))
    embedder = E5CachedEmbedder(encode, max_cached_passages=8192)
    train_x: list[list[float]] = []
    train_y: list[int] = []
    calibration: dict[str, list[float]] = {
        "e5_pos": [], "e5_neg": [],
    }
    calibration_pairs: list[tuple[list[list[float]], bool, str]] = []
    clock = time.perf_counter()
    for kind in ("multiple", "irrelevance"):
        for record in training[kind]:
            ident = record["id"]
            prefix = kind + "_"
            if type(ident) is not str or not ident.startswith(prefix):
                raise ValueError("publisher training case ID changed")
            position = int(ident[len(prefix):])
            question, funcs = parse_task(record)
            features = pair_features(question, funcs, embedder)
            expected = gold[ident] if kind == "multiple" else None
            if expected is not None and expected not in [f["name"] for f in funcs]:
                raise ValueError("publisher supported gold route not offered")
            if position % 2 == 0:
                for fn, pair in zip(funcs, features, strict=True):
                    train_x.append(pair)
                    train_y.append(int(fn["name"] == expected))
            else:
                best_e5 = max(x[0] for x in features)
                calibration["e5_pos" if expected is not None else "e5_neg"].append(
                    best_e5,
                )
                calibration_pairs.append((features, expected is not None, ident))
    if (
        len(calibration["e5_pos"]) != 100 or len(calibration["e5_neg"]) != 120
        or sum(train_y) != 100 or not any(x == 0 for x in train_y)
    ):
        raise ValueError("invalid frozen training/calibration denominators")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced", solver="liblinear",
            random_state=0, max_iter=1000,
        ),
    )
    model.fit(train_x, train_y)
    calibrated_prob: dict[str, list[float]] = {"pos": [], "neg": []}
    # The original threshold measures PER-REQUEST maxima. Keep it intact.
    # Bonferroni needs a SINGLE-CANDIDATE null, not these already-maximized
    # scores, or the larger-menu penalty is applied a second time.
    # One original negative function per held-apart original publisher
    # negative request is chosen by a frozen hash of ID alone, never score,
    # live label, offered function name or benchmark gold.
    one_per_negative_request: list[float] = []
    for feats, supported, ident in calibration_pairs:
        scores = fit_scores(feats, model)
        calibrated_prob["pos" if supported else "neg"].append(max(scores))
        if not supported:
            selector = int.from_bytes(
                hashlib.sha256(ident.encode("utf-8")).digest()[:8], "big",
            )
            one_per_negative_request.append(scores[selector % len(scores)])
    if len(one_per_negative_request) != 120:
        raise ValueError("original calibration negative request count drift")
    e5_cutoff = fixed_fpr_cutoff(calibration["e5_neg"])
    fit_cutoff = fixed_fpr_cutoff(calibrated_prob["neg"])
    eval_pos: dict[str, list[float]] = {"e5": [], "pair_fit": []}
    eval_neg: dict[str, list[float]] = {"e5": [], "pair_fit": []}
    familywise_decisions: dict[str, list[bool]] = {"pos": [], "neg": []}
    # Source-author menu sizes only; never task text or publisher gold.
    evaluated_menu_sizes: dict[str, list[int]] = {"pos": [], "neg": []}
    zero_menu_irrelevant = 0
    for kind, bucket in (("live_relevance", eval_pos),
                         ("live_irrelevance", eval_neg)):
        for record in live[kind]:
            question, funcs = parse_task(record)
            if not funcs:
                if kind != "live_irrelevance":
                    raise ValueError("publisher claims relevance with no offered function")
                # Structural no-tool is mechanically safe, but not evidence
                # that either relevance classifier recognized no-fit.
                zero_menu_irrelevant += 1
                continue
            features = pair_features(question, funcs, embedder)
            bucket["e5"].append(max(x[0] for x in features))
            candidate_fit = fit_scores(features, model)
            bucket["pair_fit"].append(max(candidate_fit))
            if menu_familywise:
                evaluated_menu_sizes[
                    "pos" if kind == "live_relevance" else "neg"
                ].append(len(funcs))
                familywise_decisions[
                    "pos" if kind == "live_relevance" else "neg"
                ].append(
                    familywise_negative_tail_accept(
                        candidate_fit, one_per_negative_request,
                    ),
                )
    if not eval_neg["e5"]:
        raise ValueError("no nonempty-menu irrelevant cases for model evaluation")
    report = {
        "study": "PUBLIC_BFCL_V4_PAIR_FIT_LIVE_CATEGORY_TRANSFER_E1",
        "source_commit": BFCL_COMMIT,
        "source_blobs": dict(LIVE_BLOBS),
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "train_even": {"supported": 100, "irrelevant": 120,
                       "individual_pairs": len(train_y)},
        "calibrate_odd": {"supported": 100, "irrelevant": 120},
        "live_category_evaluation": {
            "supported": len(eval_pos["e5"]),
            "irrelevant": len(eval_neg["e5"]) + zero_menu_irrelevant,
            "irrelevant_with_candidate_functions": len(eval_neg["e5"]),
            "irrelevant_zero_candidate_functions": zero_menu_irrelevant,
            "e5_raw_cosine": {
                "threshold_from_public_calibration": e5_cutoff,
                "calibration": stats(
                    calibration["e5_pos"], calibration["e5_neg"], e5_cutoff,
                ),
                "live": stats(eval_pos["e5"], eval_neg["e5"], e5_cutoff),
            },
            "trained_pair_fit": {
                "threshold_from_public_calibration": fit_cutoff,
                "calibration": stats(
                    calibrated_prob["pos"], calibrated_prob["neg"], fit_cutoff,
                ),
                "live": stats(
                    eval_pos["pair_fit"], eval_neg["pair_fit"], fit_cutoff,
                ),
            },
        },
        "elapsed_including_encoding_seconds": round(time.perf_counter() - clock, 2),
        "public_dataset_possible_training_contamination": True,
        "independently_authored_private_e2": False,
        "function_name_ground_truth_on_live_relevance": False,
        "actual_provider_calls": False,
        "production_threshold_calibrated": False,
        "default_product_changed": False,
        "release_qualified": False,
    }
    if menu_familywise:
        positives = familywise_decisions["pos"]
        negatives = familywise_decisions["neg"]
        if (
            len(positives) != len(eval_pos["pair_fit"])
            or len(negatives) != len(eval_neg["pair_fit"])
        ):
            raise ValueError("public BFCL family-wise cohort denominator drift")
        bins: dict[str, dict[str, dict[str, int]]] = {}
        for cohort, scores, decisions in (
            ("supported", eval_pos["pair_fit"], positives),
            ("unsupported", eval_neg["pair_fit"], negatives),
        ):
            sizes = evaluated_menu_sizes["pos" if cohort == "supported" else "neg"]
            if len(sizes) != len(scores):
                raise ValueError("BFCL original offered-menu diagnostics misaligned")
            bins[cohort] = {}
            for size, score, accepted in zip(sizes, scores, decisions, strict=True):
                bucket = (
                    "1" if size == 1 else "2-4" if size <= 4
                    else "5-12" if size <= 12 else "13+"
                )
                counts = bins[cohort].setdefault(
                    bucket, {"total": 0, "original_fit_admitted": 0,
                             "familywise_admitted": 0},
                )
                counts["total"] += 1
                counts["original_fit_admitted"] += int(score >= fit_cutoff)
                counts["familywise_admitted"] += int(accepted)
        report["live_category_evaluation"]["menu_familywise_diagnostic"] = {
            "source_menu_size_bins": bins,
            "supported_total": len(positives),
            "supported_admitted": sum(positives),
            "supported_false_refused": len(positives) - sum(positives),
            "unsupported_total": len(negatives),
            "unsupported_false_accepted": sum(negatives),
            "unsupported_correctly_refused": len(negatives) - sum(negatives),
            "familywise_alpha": 0.10,
            "source": "original_odd_id_hash_selected_single_negative_pair_Bonferroni",
            "calibration_unit": "one_function_per_original_negative_request",
            "negative_calibration_requests": len(one_per_negative_request),
            "external_independent_e2_qualified": False,
            "large_menu_unresolved_calibration_abstains": True,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--menu-familywise", action="store_true")
    args = parser.parse_args()
    old, old_shas = fetch_original_data()
    live, live_shas = load_live_source()
    # Publish only counts, never original task content or hidden source text.
    for category in ("live_relevance", "live_irrelevance"):
        counts = [len(record.get("function", [])) for record in live[category]]
        print(json.dumps({
            "publisher_category": category,
            "source_rows": len(counts),
            "empty_menus": sum(count == 0 for count in counts),
            "nonempty_menus": sum(count > 0 for count in counts),
            "largest_menu": max(counts),
        }))

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False,
        device="cpu",
    )
    def encode(texts: list[str]):  # type: ignore[no-untyped-def]
        return model.encode(
            texts, batch_size=16, show_progress_bar=False,
            normalize_embeddings=True, convert_to_numpy=True,
        )
    output = run(old, live, encode, menu_familywise=args.menu_familywise)
    output["publisher_sha256"] = {**old_shas, **live_shas}
    output["cpu_cores"] = os.cpu_count()
    output["github_run"] = os.getenv("GITHUB_RUN_ID")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps(output["live_category_evaluation"], sort_keys=True))


if __name__ == "__main__":
    main()
