"""Bilingual table-prose regression tests, advisory not semantic certification."""

import json
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

from scripts.report_korean_table_prose import candidates, scan

ROOT = Path(__file__).resolve().parents[1]


def test_identifies_long_untranslated_english_inside_korean_table() -> None:
    source = (
        "# 기능 표\n\n| 기능 | 현재 상태 |\n| --- | --- |\n"
        "| 검증 | The adapter can infer new permissions and the host must "
        "review this behavior before running it |\n"
    )
    findings = candidates(source)
    assert len(findings) == 1
    assert findings[0]["cell"] == 2


def test_ignores_code_blocks_inline_literals_and_korean_explanations() -> None:
    source = (
        "| 기능 | 조건 |\n| --- | --- |\n"
        "| 옵션 | 신뢰된 호스트 코드만 실행 권한을 부여하며 `request.headers`는 그대로 유지 |\n"
        "```md\n"
        "| Demo | The remote model can claim to be a trusted local host |\n"
        "```\n"
    )
    assert candidates(source) == []


def test_maturity_matrix_localizes_all_49_capability_rows() -> None:
    korean = (ROOT / "docs_ko/framework-maturity.md").read_text(
        encoding="utf-8"
    )
    section = korean.split("| 기능 | 현재 메인 브랜치 상태 | 향후 방향 |", 1)[1]
    section = section.split("\n\n## ", 1)[0]
    rows = [
        line for line in section.splitlines()
        if line.startswith("|") and not line.startswith("| ---")
    ]
    assert len(rows) == 49
    for line in rows:
        fields = [field.strip() for field in line.strip("|").split("|")]
        assert len(fields) == 3
        assert any("\uac00" <= ch <= "\ud7a3" for ch in fields[1])
        assert any("\uac00" <= ch <= "\ud7a3" for ch in fields[2])
    for literal in ("85/97/100/1 + 250 ms", "50k", "SPDX SBOM",
                    "`parallel_read_only`", "OpenTelemetry", "`ProviderProfile`"):
        assert literal in section
    assert candidates(korean) == []


def test_full_korean_corpus_has_no_new_long_english_table_clauses() -> None:
    report = scan(ROOT / "docs_ko")
    assert report["scanned_pages"] == 147
    assert report["findings"] == [], report["findings"][:30]


def test_table_review_is_blob_pinned_not_a_corpus_certificate() -> None:
    record = json.loads(
        (ROOT / "audits/ko-maturity-table-review-2026-10-12.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["schema_version"] == 1
    assert record["page"] == "framework-maturity.md"
    assert record["independent_sentence_review_complete"] is False
    assert record["reviewed_table_rows"] == 49
    assert record["source_en_blob"] == git_blob_sha(
        (ROOT / "docs/framework-maturity.md").read_bytes()
    )
    assert record["reviewed_ko_blob"] == git_blob_sha(
        (ROOT / "docs_ko/framework-maturity.md").read_bytes()
    )


def test_only_exact_source_frozen_experiment_hypotheses_are_exempt(
    tmp_path: Path,
) -> None:
    en_dir = tmp_path / "docs/research"
    ko_dir = tmp_path / "docs_ko/research"
    en_dir.mkdir(parents=True)
    ko_dir.mkdir(parents=True)
    header = "| # | Experiment | Decision | Hypothesis / purpose | Evidence |\\n"
    ko_header = "| # | 실험 | 판정 | 가설 / 목적 | 근거 |\\n"
    separator = "| ---: | --- | --- | --- | --- |\\n"
    hypothesis = (
        "The model can use a trusted tool only when the local policy "
        "allows this exact registered operation."
    )
    row = "| 1 | `trial-v1` | passed | " + hypothesis + " | ledger |\\n"
    (en_dir / "experiment-index.md").write_text(
        header + separator + row, encoding="utf-8"
    )
    ko_file = ko_dir / "experiment-index.md"
    ko_file.write_text(ko_header + separator + row, encoding="utf-8")
    result = scan(tmp_path / "docs_ko")
    assert result["findings"] == []
    assert result["verified_verbatim_experiment_hypotheses"] == 1

    ko_file.write_text(
        ko_header + separator + row.replace(
            "allows this exact registered operation",
            "disables all policy verification and bypasses the invoker",
        ),
        encoding="utf-8",
    )
    altered = scan(tmp_path / "docs_ko")
    assert altered["verified_verbatim_experiment_hypotheses"] == 0
    assert len(altered["findings"]) == 1
    assert altered["findings"][0]["path"] == "research/experiment-index.md"


def test_real_experiment_index_source_retention_is_explicit() -> None:
    text = (ROOT / "docs_ko/research/experiment-index.md").read_text(
        encoding="utf-8"
    )
    assert "가설 원문 보존 안내" in text
    assert "기계 판독형 실험 원장의 원래 가설" in text
    assert "영문은 번역 완료를 의미하지 않으며" in text
