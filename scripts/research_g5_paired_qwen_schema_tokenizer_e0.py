"""E0: measure actual pinned tokenizer IDs for same-success native schema menus.

Exact current principal-visible source metadata, Qwen tokenizer only;
NO model weights, generation, agent/tool execution or task cost claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from schemarouter import SchemaRouter
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    exhaustive_source_fork_reference,
)
from scripts.research_g5_multidomain_paired_k5_e0 import (
    DOMAINS,
    build_multidomain_source,
    source_scan_oracle,
)
from scripts.research_g5_source_schema_exposure_e0 import (
    MAX_K,
    SIZES,
    _visible_original_contract_bytes,
)
from scripts.research_g5_vs_scoped_lexical_k5_e0 import scoped_source_lexical_k5

SCHEMA_VERSION = "g5-paired-qwen-schema-tokenizer-e0-v1"
TOKENIZER_REPO = "Qwen/Qwen3-1.7B"
TOKENIZER_SHA = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
TOKENIZER_TRANSFORMERS = "4.57.3"


def _original_public_menu(
    router: SchemaRouter, routes: tuple[str, ...],
) -> tuple[str, int]:
    """Verified original read-only principal-scoped source schemas only."""
    if (
        not isinstance(router, SchemaRouter)
        or type(routes) is not tuple or not 1 <= len(routes) <= MAX_K
        or len(set(routes)) != len(routes)
        or any(type(route) is not str or "." not in route for route in routes)
    ):
        raise ValueError("unqualified native model source menu")
    witness = router._retrieval_authority_witness()
    policy = router._authorization_predicate(ACTOR)
    if policy is None:
        raise ValueError("original principal source authorization required")
    documents: list[str] = []
    raw_bytes = 0
    for route in sorted(routes):
        tool_key, endpoint_name = route.rsplit(".", 1)
        tool = router.registry.get(tool_key)
        matching = [ep for ep in tool.endpoints if ep.name == endpoint_name]
        if len(matching) != 1:
            raise ValueError("missing/ambiguous original native route")
        ep = matching[0]
        available = router.planner.availability_predicate
        if (
            ep.read_only is not True or ep.destructive is True
            or not policy(tool, ep)
            or (available is not None and not available(tool, ep))
        ):
            raise ValueError("unapproved source route in model schema menu")
        scoped = router._data_scope_endpoint_view(ACTOR, tool, ep)
        if scoped is None:
            raise ValueError("hidden source field/route in model schema menu")
        payload = {
            "tool": {
                "name": tool.name,
                "source_type": tool.source_type,
                "license": tool.license,
                "description": tool.description,
            },
            "endpoint": scoped.model_dump(mode="json", exclude_none=True),
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, allow_nan=False,
            separators=(",", ":"),
        )
        native_bytes = len(encoded.encode("utf-8"))
        if native_bytes != _visible_original_contract_bytes(tool, scoped):
            raise ValueError("native schema receipt serializer drift")
        documents.append(encoded)
        raw_bytes += native_bytes
    router._check_retrieval_authority_witness(witness)
    return "\n".join(documents), raw_bytes


def _encode_len(tokenizer: Any, text: str) -> int:
    if not callable(getattr(tokenizer, "encode", None)):
        raise ValueError("explicit pinned tokenizer required")
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if (
        type(tokens) not in (list, tuple) or not tokens
        or any(type(value) is not int or value < 0 for value in tokens)
    ):
        raise ValueError("tokenizer returned invalid token receipt")
    return len(tokens)


def tokenized_same_k5(
    tokenizer: Any, *, base_routes: int, mixed_scope: bool,
) -> dict[str, Any]:
    """Do not produce a cost-reduction denominator on one-sided retrieval."""
    if type(base_routes) is not int or base_routes not in SIZES:
        raise ValueError("pre-registered native source size required")
    if type(mixed_scope) is not bool:
        raise ValueError("scope flag required")
    router = build_multidomain_source(base_routes, mixed_scope=mixed_scope)
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    actual_routes = sum(len(t.endpoints) for t in router.registry.tools())
    if actual_routes != base_routes + 12:
        raise ValueError("unexpected original source size")

    cases = [("crm", GROUP, ALIASES, exhaustive_source_fork_reference(router))]
    cases.extend(
        (d.name, d.group(), d.aliases, source_scan_oracle(router, d))
        for d in DOMAINS
    )
    rows: list[dict[str, Any]] = []
    for label, group, aliases, oracle in cases:
        if len(oracle) != 1 or len(set(oracle[0])) != 3:
            raise ValueError("independent original source oracle not qualified")
        expected = set(oracle[0])
        for language, query in zip(("en", "ko", "ja"), aliases, strict=True):
            lexical, _budget = scoped_source_lexical_k5(
                router, query=query, group=group,
            )
            result = graph.lookup_shared_root_forks(
                router, query, group=group, principal=ACTOR, k=MAX_K,
            )
            got = tuple(
                (row.root_route_id, *row.branch_route_ids)
                for row in result.candidates
            )
            if (
                result.status != "complete"
                or result.requested_k != MAX_K
                or got != oracle
                or result.executable_authority
                or result.independent_quality_evidence
            ):
                raise ValueError("G5 source-attested original path not qualified")
            g5_routes = tuple(sorted(set(route for path in got for route in path)))
            if len(g5_routes) != 3 or len(lexical) > MAX_K:
                raise ValueError("invalid original K5 route budget")
            lex_ok = expected.issubset(lexical)
            g5_ok = expected.issubset(g5_routes)
            g5_json, g5_raw_bytes = _original_public_menu(router, g5_routes)
            lex_json, lex_raw_bytes = _original_public_menu(router, lexical) if lexical else ("", 0)
            shared_complete = lex_ok and g5_ok
            rows.append({
                "domain": label,
                "language": language,
                "g5_source_complete": g5_ok,
                "lexical_source_complete": lex_ok,
                "shared_complete_cost_eligible": shared_complete,
                "g5_route_count": len(g5_routes),
                "lexical_route_count": len(lexical),
                "g5_original_schema_bytes": g5_raw_bytes,
                "lexical_original_schema_bytes": lex_raw_bytes,
                "g5_native_schema_json_tokens": _encode_len(tokenizer, g5_json),
                "lexical_native_schema_json_tokens": (
                    _encode_len(tokenizer, lex_json) if lexical else 0
                ),
                "g5_serialized_menu_sha256": hashlib.sha256(
                    g5_json.encode("utf-8")
                ).hexdigest(),
                "lexical_serialized_menu_sha256": hashlib.sha256(
                    lex_json.encode("utf-8")
                ).hexdigest(),
            })
    qualified = [row for row in rows if row["shared_complete_cost_eligible"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_tier": "E0_MODEL_TOKENIZER_ONLY_NO_AGENT",
        "tokenizer_repository": TOKENIZER_REPO,
        "tokenizer_revision": TOKENIZER_SHA,
        "tokenizer_transformers_version": TOKENIZER_TRANSFORMERS,
        "tokenizer_add_special_tokens": False,
        "base_registered_routes": base_routes,
        "actual_registered_native_routes": actual_routes,
        "mixed_scope": mixed_scope,
        "strict_k": MAX_K,
        "rows": rows,
        "qualified_paired_cases": len(qualified),
        "paired_g5_native_json_tokens": sum(
            row["g5_native_schema_json_tokens"] for row in qualified
        ),
        "paired_lexical_native_json_tokens": sum(
            row["lexical_native_schema_json_tokens"] for row in qualified
        ),
        "original_provider_callbacks": False,
        "model_weights_loaded": False,
        "actual_agent_final_task_measured": False,
        "entire_model_prompt_or_completion_tokens_measured": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    import transformers
    from transformers import AutoTokenizer

    if transformers.__version__ != TOKENIZER_TRANSFORMERS:
        raise ValueError("unregistered transformers tokenizer version")
    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_REPO, revision=TOKENIZER_SHA, trust_remote_code=False,
    )
    results = [
        tokenized_same_k5(tokenizer, base_routes=size, mixed_scope=scope)
        for size in SIZES for scope in (False, True)
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "cases": results,
        "tokenizer_repository": TOKENIZER_REPO,
        "tokenizer_revision": TOKENIZER_SHA,
        "transformers_version": TOKENIZER_TRANSFORMERS,
        "paired_tokenizer_tokens_are_full_agent_cost": False,
        "independent_e2_qualified": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        report, sort_keys=True, ensure_ascii=False, indent=2,
        allow_nan=False,
    ) + "\n", encoding="utf-8")
    print(json.dumps({
        "measured_cases": sum(len(x["rows"]) for x in results),
        "qualified_paired_cases": sum(x["qualified_paired_cases"] for x in results),
        "independent_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
