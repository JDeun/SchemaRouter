"""Revision-pinned Korean security-policy editorial review: not a corpus certificate."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "audits" / "ko-security-policy-review-2026-10-10.json"
EN_PATH = ROOT / "docs" / "security" / "threat-model.md"
KO_PATH = ROOT / "docs_ko" / "security" / "threat-model.md"


def test_security_policy_review_is_tied_to_exact_source_and_translation() -> None:
    review = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert review["scope"].startswith("docs/security/threat-model.md")
    assert "not established" in review["review_type"]
    assert "other 146 pairs" in review["conclusion"]
    assert review["source_en_blob"] == git_blob_sha(EN_PATH.read_bytes())
    assert review["reviewed_ko_blob"] == git_blob_sha(KO_PATH.read_bytes())


def test_security_policy_translation_retains_full_section_structure() -> None:
    headings = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
    source = EN_PATH.read_text(encoding="utf-8")
    translated = KO_PATH.read_text(encoding="utf-8")
    assert [len(m.group(1)) for m in headings.finditer(source)] == [
        len(m.group(1)) for m in headings.finditer(translated)
    ]


def test_security_policy_has_no_untranslated_document_authority_paragraph() -> None:
    korean = KO_PATH.read_text(encoding="utf-8")
    assert "Documentation text is treated as untrusted" not in korean
    assert "script/style content is removed before model" not in korean
    assert "문서 텍스트는 신뢰할 수 없는 입력" in korean
    assert "모델이 분석하기 전에 스크립트와 스타일 콘텐츠를 제거" in korean
    assert "근거 확인(grounding)과 명시적 승인 절차" in korean


def test_security_policy_critical_negations_and_literals_are_preserved() -> None:
    korean = KO_PATH.read_text(encoding="utf-8")
    required = (
        "권한의 근거가 아닙니다",
        "신뢰된 로컬 정책을 요구",
        "수신 대상의 예외 때문에 허용 판정을",
        "authorization_audit_delivery_mode=\"strict\"",
        "AuthorizationAuditDeliveryError",
        "PolicyViolationError",
        "모델에 노출되는 도구 인수 밖",
        "Mcp-*",
        "stale_source",
        "stale_contract",
        "DNS 리바인딩",
        "16 MiB",
        "RunConfig(include_payloads=True)",
        "NonRetryableInvocationError",
        "SchemaRouter.amend_capability()",
        "MCPClientFactory",
    )
    for phrase in required:
        assert phrase in korean, phrase


def test_korean_retry_and_hook_prose_keeps_original_safety_contract() -> None:
    korean = KO_PATH.read_text(encoding="utf-8")
    # A successful tool must not be retried because an observer failed.
    assert "실행 후 훅의 실패는 재시도 가능한 도구 실행 실패로 분류하지 않으므로" in korean
    assert "비어 있지 않은 명시적 허용 목록" in korean
    assert "읽기 전용으로 분류된 엔드포인트로 제한됩니다" in korean
    assert "그 밖의 HTTP 오류나 결정적인 응답 계약 위반에서는 즉시 실패" in korean
    assert "`NonRetryableInvocationError`" in korean
    assert "예산 초과로 거부된 호출과 스키마 계약 위반은 재시도하지 않습니다" in korean
    assert "신뢰된 로컬 실행 코드이며, 민감값을 제거한 원격 측정 데이터가 아닙니다" in korean
    assert "실행 전 훅은 검증된 인수 값을" in korean
    assert "실행 후 훅은 최종 투영된 결과 본문" in korean
    assert "신뢰할 수 없는 원격 또는 제3자 콜백에 전달하지 마십시오" in korean
    assert "인수 값, 결과 본문, RunConfig 메타데이터, 태그 및 예외 메시지는 내보내지 않습니다" in korean
    for leftover in (
        "Automatic retry는 trusted local code",
        "Built-in OpenAPI/OPTIMADE HTTP invoker는",
        "Before/after execution hook은 trusted local executable code",
        "Before hook은 validated argument value",
        "Optional OpenTelemetry exporter는 더 엄격합니다",
    ):
        assert leftover not in korean
