"""Guard reviewed decision-backend EN/KO tradeoffs; not an independent corpus certificate."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/concepts/decision-backends.md"
TRANSLATED = ROOT / "docs_ko/concepts/decision-backends.md"
REVIEW = ROOT / "audits/ko-decision-backends-review-2026-10-12.json"


def test_decision_backend_review_is_revision_pinned_and_limited() -> None:
    record = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["path"] == "concepts/decision-backends.md"
    assert record["independent_sentence_review_complete"] is False
    assert record["reviewed_sections"] == 4
    assert "independent human" in record["reviewer_status"]
    assert record["en_blob"] == git_blob_sha(SOURCE.read_bytes())
    assert record["ko_blob"] == git_blob_sha(TRANSLATED.read_bytes())


def test_backend_comparison_has_six_localized_rows_with_original_tradeoffs() -> None:
    ko = TRANSLATED.read_text(encoding="utf-8")
    section = ko.split("## 결정 백엔드 선택\n", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("|")]
    assert len(lines) == 8  # heading, separator, and all six original backend rows
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 3
        assert re.search("[가-힣]", cells[1]), line
        assert re.search("[가-힣]", cells[2]), line

    for contract in (
        "모델·런타임 운영과 점수 보정은 애플리케이션의 책임",
        "구조화 출력 프롬프트 및 인증정보를 애플리케이션에서 관리",
        "현재 단일 선택 어댑터만 지원",
        "체크포인트·도메인에 따라 달라짐",
        "전용 결정 모델보다 연산이 무겁고 느림",
        "외부 서비스·네트워크에 의존",
    ):
        assert contract in section


def test_non_code_english_remnants_are_translated() -> None:
    ko = TRANSLATED.read_text(encoding="utf-8")
    assert "Enable field selection explicitly:" not in ko
    assert "A decision provider:" not in ko
    assert "The packaged extra is " not in ko
    assert "필드 선택은 다음과 같이 명시적으로 활성화합니다" in ko
    assert "의사결정 백엔드는 다음 계약을 준수해야 합니다" in ko
    assert "배포된 패키지의 선택적 추가 의존성 이름은 `schemarouter[laya]`" in ko
