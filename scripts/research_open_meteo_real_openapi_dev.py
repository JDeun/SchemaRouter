"""Source-pinned real provider OpenAPI adapter/retrieval *DEV*, zero API calls.

Reads *exact* publisher-authored Open-Meteo YAML, not a ChatGPT reconstructed
mock. Queries are OUR author-written development prompts, NOT disjoint labels.
Parser errors remain archived negative evidence and do not authorize release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    InMemoryRegistry,
    PlanRequest,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.adapters.openapi import tool_from_openapi

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAMES = (
    "air-quality", "climate", "elevation", "ensemble", "flood",
    "forecast", "historical-weather", "marine", "seasonal",
)
# Independently authored by THIS research author, NOT a provider-labeled or
# blind benchmark. One target source file per supported query.
QUERIES = {
    "air-quality": (
        "Look up the PM2.5 and air quality forecast for this city.",
        "이 도시의 초미세먼지와 대기질 예보를 조회하세요.",
        "この都市のPM2.5と大気質の予報を取得してください。",
    ),
    "climate": (
        "Examine the long-term climate change projections from CMIP6.",
        "CMIP6 장기 기후변화 전망을 조사해 주세요.",
        "CMIP6の長期気候変動予測を調べてください。",
    ),
    "elevation": (
        "Retrieve terrain elevation for a given latitude and longitude.",
        "위도와 경도에 따른 지형 고도를 조회해 주세요.",
        "緯度と経度から地形の標高を取得してください。",
    ),
    "ensemble": (
        "Get ensemble weather forecasts from several prediction models.",
        "여러 예측 모델의 앙상블 날씨 예보를 조회하세요.",
        "複数モデルのアンサンブル気象予報を取得してください。",
    ),
    "flood": (
        "Read the river discharge flood forecast for next week.",
        "다음 주 하천 유량과 홍수 예보를 조회하세요.",
        "来週の河川流量と洪水予測を取得してください。",
    ),
    "forecast": (
        "Get tomorrow's hourly temperature and rain weather forecast.",
        "내일 시간대별 기온과 강수 날씨 예보를 조회하세요.",
        "明日の時間別気温と降水の天気予報を取得してください。",
    ),
    "historical-weather": (
        "Find historical daily weather observations from 1980.",
        "1980년의 과거 일별 기상 관측값을 찾으세요.",
        "1980年の過去の日別気象観測値を調べてください。",
    ),
    "marine": (
        "Read marine wave height and ocean current predictions.",
        "해양 파고와 해류 예측값을 조회하세요.",
        "海の波高と海流の予測値を取得してください。",
    ),
    "seasonal": (
        "Check the seasonal weather forecast six months ahead.",
        "6개월 뒤의 계절별 날씨 전망을 조회하세요.",
        "6か月先の季節予報を取得してください。",
    ),
}
UNSUPPORTED = (
    ("delete", "Permanently delete the saved climate records.",
     "저장된 기후 기록을 영구 삭제하세요.",
     "保存された気候記録を完全に削除してください。"),
    ("transfer", "Transfer cash from my account to another user.",
     "내 계좌에서 다른 사람에게 돈을 송금하세요.",
     "自分の口座から別の人へ送金してください。"),
    ("purchase", "Purchase a paid flight ticket and issue its confirmation.",
     "유료 항공권을 구매하고 예약을 확정하세요.",
     "有料の航空券を購入して予約を確定してください。"),
)
LANGUAGES = ("en", "ko", "ja")
SOURCE_COMMIT = "b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4"


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode() + payload,
    ).hexdigest()


def load_contracts(
    manifest_path: Path, data_dir: Path,
) -> tuple[list[Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("provider_repository") != "open-meteo/open-meteo"
        or manifest.get("source_commit") != SOURCE_COMMIT
        or manifest.get("real_provider_authored_spec") is not True
        or manifest.get("independently_authored_query_labels") is not False
        or manifest.get("may_release") is not False
        or set(manifest.get("docs", {})) != set(SOURCE_NAMES)
    ):
        raise ValueError("unregistered publisher/source provenance")
    tools, problems = [], []
    evidence: dict[str, Any] = {}
    for name in SOURCE_NAMES:
        source = manifest["docs"][name]
        if source["path"] != f"openapi/{name}.yml":
            raise ValueError("unregistered publisher file path")
        payload = (data_dir / f"{name}.yml").read_bytes()
        observed = git_blob_sha1(payload)
        if observed != source["git_blob_sha1"]:
            raise ValueError(f"publisher YAML byte drift: {name}")
        evidence[name] = {
            "git_blob_sha1": observed,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        doc = yaml.safe_load(payload)
        if (
            type(doc) is not dict or not str(doc.get("openapi", "")).startswith("3.")
            or not isinstance(doc.get("paths"), dict)
        ):
            raise ValueError(f"invalid publisher OpenAPI: {name}")
        route = f"open_meteo_{name.replace('-', '_')}"
        try:
            tool = tool_from_openapi(route, doc)
            if not tool.endpoints:
                raise ValueError("adapter returned no endpoints")
            if any(not endpoint.read_only for endpoint in tool.endpoints):
                raise ValueError("GET-only author fixture must not include mutations")
            tools.append(tool)
            evidence[name]["route_ids"] = [
                f"{tool.key}.{endpoint.name}" for endpoint in tool.endpoints
            ]
            evidence[name]["status"] = "parsed"
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            evidence[name]["status"] = "adapter_failed"
            evidence[name]["error"] = f"{type(exc).__name__}: {exc}"[:450]
            problems.append({"source": name, "error": evidence[name]["error"]})
    return tools, problems, evidence


def evaluate(
    manifest_path: Path, data_dir: Path,
) -> dict[str, Any]:
    tools, problems, evidence = load_contracts(manifest_path, data_dir)
    if not tools:
        raise ValueError("no authentic provider source parsed successfully")
    registry = InMemoryRegistry()
    registry.update_many(tools)
    registered = {
        f"{tool.key}.{ep.name}"
        for tool in registry.tools() for ep in tool.endpoints
    }
    if len(registered) != sum(len(tool.endpoints) for tool in tools):
        raise ValueError("duplicate official provider route identities")
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="publisher-dev-get-only",
                effect="allow", operation="open_meteo_*.*",
                roles_any=("viewer",),
            ),
        ),
        default_effect="deny",
    )
    router = SchemaRouter(registry=registry, authorization_policy=policy)
    principal = PrincipalContext(subject="synthetic-public-provider-dev", roles=("viewer",))
    by_source = {
        n: evidence[n].get("route_ids", [])
        for n in SOURCE_NAMES
    }
    rows: list[dict[str, Any]] = []
    for source in SOURCE_NAMES:
        if evidence[source]["status"] != "parsed":
            continue
        for language, query in zip(LANGUAGES, QUERIES[source], strict=True):
            start = time.perf_counter_ns()
            answer = router.retrieve_authorized(
                PlanRequest(query=query), principal=principal, k=9,
            )
            elapsed = (time.perf_counter_ns() - start) / 1e6
            ids = [c.route_id for c in answer.candidates]
            if (
                not math.isfinite(elapsed) or elapsed < 0
                or len(ids) > 9 or len(ids) != len(set(ids))
                or not set(ids).issubset(registered)
            ):
                raise ValueError("source-backed authorized public API invalid")
            rows.append({
                "source": source, "language": language,
                "kind": "supported", "target_route_ids": by_source[source],
                "top1": ids[0] if ids else None, "top5": ids[:5],
                "any_source_target_top1": bool(ids and ids[0] in by_source[source]),
                "any_source_target_top5": bool(
                    set(ids[:5]).intersection(by_source[source])
                ),
                "duration_ms": round(elapsed, 5),
                "no_tool_execution": True,
            })
    unsupported_rows = []
    for name, *queries in UNSUPPORTED:
        for language, query in zip(LANGUAGES, queries, strict=True):
            answer = router.retrieve_authorized(
                PlanRequest(query=query), principal=principal, k=9,
            )
            ids = [c.route_id for c in answer.candidates]
            if len(ids) > 9 or not set(ids).issubset(registered):
                raise ValueError("unauthorized or overwide negative shortlist")
            unsupported_rows.append({
                "kind": "unsupported", "source": name, "language": language,
                "retrieval_nonempty": bool(ids),
                "no_fit_verifier_exercised": False,
                "tool_executed": False,
            })
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, timeout=10, check=True,
    ).stdout.strip()
    report = {
        "schema_version": 1,
        "study": "source_authored_open_meteo_actual_openapi_adapter_dev",
        "repo_source_commit": git_commit,
        "external_provider_commit": SOURCE_COMMIT,
        "provider_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "provider_files": evidence,
        "parser_failures": problems,
        "total_real_provider_contracts": len(SOURCE_NAMES),
        "parsed_tools": len(tools),
        "registered_routes": len(registered),
        "supported_cases": len(rows),
        "unsupported_cases": len(unsupported_rows),
        "supported_top1_source_match": sum(
            r["any_source_target_top1"] for r in rows
        ),
        "supported_top5_source_match": sum(
            r["any_source_target_top5"] for r in rows
        ),
        "unsupported_nonempty_retrieval": sum(
            r["retrieval_nonempty"] for r in unsupported_rows
        ),
        "cases": rows + unsupported_rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "scope": {
            "actual_external_provider_published_schemas": True,
            "untrusted_author_authored_multilingual_queries": True,
            "independently_labelled_queries": False,
            "auth_principal_simulated_not_authenticated": True,
            "tool_or_live_api_invocations": False,
            "semantic_no_fit_proven": False,
            "agent_task_success": False,
            "independent_release_validation": False,
            "may_release": False,
        },
    }
    if len(rows) != len(tools) * len(LANGUAGES) and not problems:
        raise ValueError("partial publisher-derived positive matrix")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.manifest, args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["study"],
        "parsed": result["parsed_tools"],
        "parser_failures": len(result["parser_failures"]),
        "supported_cases": result["supported_cases"],
        "unsupported_cases": result["unsupported_cases"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
