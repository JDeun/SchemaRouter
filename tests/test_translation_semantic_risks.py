"""Regression coverage for bilingual semantic-literal risk triage."""

from pathlib import Path

from scripts.report_translation_semantic_risks import prose, scan, tokens


def test_code_fences_excluded_and_prose_checked() -> None:
    content = (
        "# Title\n\nUse \x60router.ainvoke()\x60 at 95%.\n\n"
        "\x60\x60\x60python\nvalue = 123\n\x60\x60\x60\n"
    )
    found = tokens(content)
    assert "router.ainvoke()" in found["technical"]
    assert "95%" in found["numbers"]
    assert "123" not in found["numbers"]


def test_missing_values_are_only_risk_candidates(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "guide.md").write_text("# Test\n\nUse \x60safe_mode=True\x60 at 99%.", encoding="utf-8")
    (ko / "guide.md").write_text("# 검증\n\n안전하게 사용하십시오.", encoding="utf-8")
    report = scan(en, ko)
    assert report["paired_pages"] == 1
    assert report["flagged_pages"] == 1
    missing = report["flags"][0]["source_only"]
    assert "safe_mode=True" in missing["technical"]
    assert "99%" in missing["numbers"]
    assert "NOT semantic equivalence certification" in report["scope"]


def test_tilde_fence_is_stripped() -> None:
    assert "123" not in prose("# Header\n\n~~~bash\n123\n~~~\n")


def test_korean_particles_and_number_separator_do_not_look_missing() -> None:
    english = tokens("# Results\n\n158 of 181 instances and 1,200 queries.")
    korean = tokens("# 결과\n\n181개 중 158개와 1200개 질의.")
    assert english["numbers"] <= korean["numbers"]
