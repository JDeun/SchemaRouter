"""Source-pinned public BFCL V4 route-choice/no-tool diagnostic (E1, not E2).

Predict function NAME only, not argument AST or native execution. 200 externally
authored multiple-choice + 240 irrelevance cases, entirely external *public*
dataset, not independent private model holdout or multilingual confirmation.
No model is tuned/selected based on these cases, no product defaults change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any

from schemarouter import (
    E5CachedEmbedder, EmbeddingDecisionBackend, EndpointSpec, FieldSpec,
    SchemaRouter, ToolSpec,
)
from schemarouter.decisions import DecisionOption, DecisionRequest, choose_sync

BFCL_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
ROOT = (
    "https://raw.githubusercontent.com/ShishirPatil/gorilla/"
    + BFCL_COMMIT + "/berkeley-function-call-leaderboard/bfcl_eval/data/"
)
MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
ORIGINAL_FILES = {
    "multiple": ("BFCL_v4_multiple.json",
                 "83643fa853e7a29a50e7303b0279284c37dd63c8", 200),
    "irrelevance": ("BFCL_v4_irrelevance.json",
                    "0077629949f2d52734cef2f110b0d040d8c47554", 240),
    "gold": ("possible_answer/BFCL_v4_multiple.json",
             "1f2f1fbfd9b7c8859ef5a92d6c18b0a6b2bc2663", 200),
}
STOPWORDS = frozenset((
    "a an the and or to of by on in at with for from how what which is are "
    "can do does me i you my your this that given using use get find show "
    "please calculate compute function value values result results return"
).split())


def _sha1_git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\\0" + raw,
    ).hexdigest()


def _parse_jsonl(raw: bytes, key: str, count: int) -> list[dict[str, Any]]:
    if len(raw) > 2_000_000:
        raise ValueError("BFCL publisher file exceeds pinned safety cap")
    try:
        entries = [json.loads(line) for line in raw.decode("utf-8").splitlines()
                   if line.strip()]
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("BFCL original data JSONL invalid") from exc
    if len(entries) != count or {x.get("id") for x in entries} != {
        f"{key}_{i}" for i in range(count)
    }:
        raise ValueError("BFCL source original cohort changed")
    return entries


def fetch_original_data() -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    data: dict[str, list[dict[str, Any]]] = {}
    hashes: dict[str, str] = {}
    for key, (path, expected_git_blob, count) in ORIGINAL_FILES.items():
        with urllib.request.urlopen(ROOT + path, timeout=30) as response:
            raw = response.read(2_000_001)
        if _sha1_git_blob(raw) != expected_git_blob:
            raise ValueError(f"BFCL {key} upstream original source blob drift")
        data[key] = _parse_jsonl(
            raw, "multiple" if key == "gold" else key, count,
        )
        hashes[key] = hashlib.sha256(raw).hexdigest()
    return data, hashes


def _words(text: str) -> set[str]:
    de_camel = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    normalized = unicodedata.normalize("NFKC", de_camel).casefold()
    return {
        token for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) >= 3 and token not in STOPWORDS
    }


def _source_text(fn: dict[str, Any]) -> str:
    params = fn.get("parameters", {})
    properties = params.get("properties", {})
    fields = []
    if type(properties) is dict:
        for name, field in properties.items():
            if type(name) is str and type(field) is dict:
                fields.append(name + " " + str(field.get("description", "")))
    return " ".join([fn["name"], fn["description"], *fields])


def host_visible_lexical_choice(
    query: str, functions: list[dict[str, Any]],
) -> str | None:
    """Actual library lexical retrieval, not a stand-in scorer."""
    router = SchemaRouter()
    lookup: dict[str, str] = {}
    for index, fn in enumerate(functions):
        tool_name = f"bfcl_func_{index:02d}"
        router.add_tool(ToolSpec(
            name=tool_name, description=fn["name"] + " " + fn["description"],
            endpoints=[EndpointSpec(
                name="invoke",
                description=fn["description"],
                read_only=True, destructive=False,
                output_fields=[FieldSpec(name="result")],
            )],
        ))
        lookup[tool_name + ".invoke"] = fn["name"]
    result = router.retrieve(query, k=1)
    return lookup[result.candidates[0].route_id] if result.candidates else None


def evidence_only_lexical_guard(
    query: str, selected: str | None, functions: list[dict[str, Any]],
) -> str | None:
    """Predeclared conservative 2-token overlap; no learned cutoff.

    This simple proposed abstention must be scored for both false refusals
    and false accepts; it is NOT a calibrated safety guard or default.
    """
    if selected is None:
        return None
    matched = next((fn for fn in functions if fn["name"] == selected), None)
    if matched is None:
        raise ValueError("selected function not in original source")
    return (
        selected if len(_words(query) & _words(_source_text(matched))) >= 2
        else None
    )


def e5_source_choice(
    query: str, functions: list[dict[str, Any]],
    backend: EmbeddingDecisionBackend,
) -> str | None:
    options = [
        DecisionOption(
            id=f"visible:{i}", label=fn["name"],
            description=fn["description"] + " " + _source_text(fn),
        )
        for i, fn in enumerate(functions)
    ]
    # The externally authored truth/function ID is not fed as model gold.
    prediction = choose_sync(
        backend, DecisionRequest(
            query=query, options=options, max_selections=1,
            context={"surface": "external_public_bfcl_v4_e1_only"},
        ),
    )
    if prediction.abstained or not prediction.selections:
        return None
    matched = int(prediction.selections[0].option_id.split(":", 1)[1])
    if not 0 <= matched < len(functions):
        raise ValueError("unregistered model function index")
    return functions[matched]["name"]


def run_bfcl(
    data: dict[str, list[dict[str, Any]]],
    backend: EmbeddingDecisionBackend,
) -> dict[str, Any]:
    gold = {
        x["id"]: tuple(x["ground_truth"][0])
        for x in data["gold"]
    }
    if len(gold) != 200 or any(len(value) != 1 for value in gold.values()):
        raise ValueError("unrecognized original publisher gold")
    metrics = {
        key: {
            "supported_correct": 0, "supported_false_refusal": 0,
            "supported_wrong_function": 0, "unsupported_safe_refusal": 0,
            "unsupported_false_accept": 0,
        }
        for key in ("lexical", "lexical_guard", "e5", "e5_guard")
    }
    latencies: dict[str, list[float]] = {key: [] for key in metrics}
    for cohort in ("multiple", "irrelevance"):
        for row in data[cohort]:
            question = row["question"]
            if (
                type(question) is not list or len(question) != 1
                or type(question[0]) is not list or len(question[0]) != 1
                or question[0][0].get("role") != "user"
            ):
                raise ValueError("BFCL multiple/irrelevance conversation changed")
            query = question[0][0]["content"]
            functions = row["function"]
            if not (
                type(query) is str and query.strip()
                and type(functions) is list
                and 1 <= len(functions) <= 4
                and all(type(fn) is dict and type(fn.get("name")) is str
                        and type(fn.get("description")) is str
                        for fn in functions)
            ):
                raise ValueError("untrusted BFCL original function schema")
            expected = gold[row["id"]] if cohort == "multiple" else ()
            if expected and not set(expected).issubset(
                {fn["name"] for fn in functions}
            ):
                raise ValueError("publisher gold not offered in candidate set")
            t0 = time.perf_counter_ns()
            lexical = host_visible_lexical_choice(query, functions)
            latencies["lexical"].append((time.perf_counter_ns() - t0) / 1e6)
            t0 = time.perf_counter_ns()
            guarded_lexical = evidence_only_lexical_guard(
                query, lexical, functions,
            )
            latencies["lexical_guard"].append(
                (time.perf_counter_ns() - t0) / 1e6
            )
            t0 = time.perf_counter_ns()
            semantic = e5_source_choice(query, functions, backend)
            latencies["e5"].append((time.perf_counter_ns() - t0) / 1e6)
            t0 = time.perf_counter_ns()
            guarded_e5 = evidence_only_lexical_guard(
                query, semantic, functions,
            )
            latencies["e5_guard"].append((time.perf_counter_ns() - t0) / 1e6)
            for arm, prediction in (
                ("lexical", lexical), ("lexical_guard", guarded_lexical),
                ("e5", semantic), ("e5_guard", guarded_e5),
            ):
                counter = metrics[arm]
                if cohort == "irrelevance":
                    counter[
                        "unsupported_safe_refusal" if prediction is None
                        else "unsupported_false_accept"
                    ] += 1
                else:
                    counter[
                        "supported_false_refusal" if prediction is None
                        else (
                            "supported_correct" if prediction in expected
                            else "supported_wrong_function"
                        )
                    ] += 1
    if any(
        x["supported_correct"] + x["supported_wrong_function"]
        + x["supported_false_refusal"] != 200
        or x["unsupported_safe_refusal"] + x["unsupported_false_accept"] != 240
        for x in metrics.values()
    ):
        raise ValueError("incomplete benchmark outcome or scored denominator")
    return {
        "evidence": "EXTERNAL_PUBLISHER_PUBLIC_BFCL_V4_E1_DIAGNOSTIC_ONLY",
        "publisher_commit": BFCL_COMMIT,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "supported_multiple": 200,
        "unsupported_irrelevance": 240,
        "operation": "FUNCTION_NAME_ONLY_NOT_ARGUMENT_AST",
        "results": {
            arm: {
                **counts,
                "inference_ms_p50": round(statistics.median(latencies[arm]), 2),
                "inference_ms_p95": round(sorted(latencies[arm])[
                    math.ceil(.95 * len(latencies[arm])) - 1], 2),
            }
            for arm, counts in metrics.items()
        },
        "no_real_provider_tool_execution": True,
        "independent_private_holdout": False,
        "native_provider_e2_qualified": False,
        "unsupported_abstention_calibrated": False,
        "model_promoted": False,
        "release_qualified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data, hashes = fetch_original_data()
    from sentence_transformers import SentenceTransformer

    import torch

    torch.set_num_threads(4)
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False,
        device="cpu",
    )
    def encode(texts: list[str]):  # type: ignore[no-untyped-def]
        return model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True,
            show_progress_bar=False, batch_size=8,
        )
    backend = EmbeddingDecisionBackend(E5CachedEmbedder(encode))
    output = run_bfcl(data, backend)
    output["publisher_git_blob_sha1"] = {
        key: ORIGINAL_FILES[key][1] for key in ORIGINAL_FILES
    }
    output["publisher_file_sha256"] = hashes
    output["github_actions_run_id"] = os.getenv("GITHUB_RUN_ID")
    output["runtime"] = {
        "cpu_count": os.cpu_count(), "python": platform.python_version(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    print(json.dumps({
        "category_denominators": [200, 240],
        "results": output["results"],
        "native_provider_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
