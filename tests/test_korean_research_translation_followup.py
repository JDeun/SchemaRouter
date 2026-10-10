"""Pin targeted EN/KO research & release translations; not a corpus certificate."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "audits" / "ko-research-translation-followup-2026-10-10.json"


def test_revision_pinned_research_translation_review() -> None:
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert len(data["reviewed"]) == 5
    assert "not 147-pair" in data["scope"]
    for entry in data["reviewed"]:
        assert entry["en_blob"] == git_blob_sha(
            (ROOT / "docs" / entry["path"]).read_bytes()
        ), entry["path"]
        assert entry["ko_blob"] == git_blob_sha(
            (ROOT / "docs_ko" / entry["path"]).read_bytes()
        ), entry["path"]


def test_frozen_stop_rules_and_negative_results_are_not_lost() -> None:
    history = (
        ROOT / "docs_ko/research/design-and-experiment-history.md"
    ).read_text(encoding="utf-8")
    assert "1,019건" in history and "**1,046건**" in history
    assert "추가 개선 여지 27건" in history
    assert "사후" in history and "중단 규칙" in history
    assert "결과 확인 후 추가하는 수작업 규칙" in history
    assert "거부권만 행사하는 권한 경계" in history
    assert "모델 품질이 나쁘다는 실험 증거는 아닙니다" in history
    assert "실패한 신규 확인 데이터" in history
    assert "모든 지원 사례에서 올바른 도구" in history
    for untranslated in (
        "Do not continue with finer scalar thresholds",
        "The server log shows correct-but-slow",
        "Per preregistration, it is not repaired",
        "On this new DEV, the raw BGE ranker",
        "Holding the global 0.55 weight produced",
    ):
        assert untranslated not in history


def test_nli_confirmation_still_explicitly_unscored() -> None:
    status = (ROOT / "docs_ko/research/routing-status.md").read_text(
        encoding="utf-8"
    )
    assert "별도로 동결한 확인용 데이터셋은 아직 **채점하지 않았습니다**" in status
    assert "The exact formulation is terminal" not in status


def test_release_hooks_and_elapsed_time_keep_safety_limits() -> None:
    r04 = (ROOT / "docs_ko/releases/0.4.0.md").read_text(encoding="utf-8")
    r05 = (ROOT / "docs_ko/releases/0.5.0.md").read_text(encoding="utf-8")
    assert "훅은 호출이나 결과를 변경할 수 없으며" in r04
    assert "훅 실패는 재시도하지 않고" in r04
    assert "스키마와 바인딩 상태를 다시 확인합니다" in r04
    assert "신뢰된 실행 전후 훅의 시간도 포함됩니다" in r05
    assert "Trusted before/after hook" not in r04
    assert "Trusted middleware가 run-level wall-clock" not in r05


def test_architecture_local_authority_and_trace_privacy_remain_explicit() -> None:
    architecture = (ROOT / "docs_ko/architecture.md").read_text(
        encoding="utf-8"
    )
    assert "Jev에는 `DecisionOption.metadata`도 전달하지 않습니다" in architecture
    assert "누락된 증거를 충족한 것으로 바꿀 수 없습니다" in architecture
    assert "실행 후 훅의 오류를 도구 자체의 오류로 간주해 재시도하지 않습니다" in architecture
    assert "추적 데이터베이스는 원본 이벤트 스트림의 개인정보 보호 수준" in architecture
    assert "include_payloads=True" in architecture
    assert "For evidence\\nEvidence sufficiency" not in architecture
    assert "Trace database는 source event의 privacy level을 보존합니다 stream" not in architecture
