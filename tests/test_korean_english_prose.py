"""English-prose leakage is a review queue, never a semantic equivalence score."""

from pathlib import Path

from scripts.report_korean_english_prose import candidates, scan

ROOT = Path(__file__).resolve().parents[1]


def test_catches_english_contract_clause_spliced_into_korean_prose() -> None:
    sample = (
        "# 보안 정책\n"
        "모델에는 검증이 필요합니다. This option does not grant authority "
        "and the model must not execute an unapproved remote operation.\n"
    )
    matches = candidates(sample)
    assert len(matches) == 1
    assert matches[0]["line"] == 2
    assert matches[0]["english_function_words"] >= 2


def test_ignores_code_literals_and_cited_english_paper_titles() -> None:
    sample = (
        "# 참고문헌\n"
        "[*The best way to train and evaluate this new classifier*]"
        "(https://example.org/paper)\n\n"
        "~~~text\n"
        "The model does not execute unapproved operations before authorization.\n"
        "~~~\n\n"
        "\x60The model does not execute unapproved operations before authorization\x60\n"
    )
    assert candidates(sample) == []


def test_security_policy_no_long_english_contract_leakage() -> None:
    source = ROOT / "docs_ko" / "security" / "threat-model.md"
    assert candidates(source.read_text(encoding="utf-8")) == []


def test_report_never_claims_a_semantic_certificate(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text(
        "# Test\n\nThis language is English and must be reviewed before it "
        "can be accepted as an equivalent translation.\n",
        encoding="utf-8",
    )
    report = scan(tmp_path)
    assert report["scanned_pages"] == 1
    assert report["candidate_lines"] == 1
    assert "NOT semantic equivalence" in report["scope"]
