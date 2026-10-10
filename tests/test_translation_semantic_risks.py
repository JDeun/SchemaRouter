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


def test_percent_point_notations_are_semantically_equal() -> None:
    english = tokens("# Difference\n\nK3 delta: -3.26pp; gate: -2pp; CI 95%.")
    korean = tokens("# 차이\n\nK3 차이 -3.26%p, 게이트 -2%포인트, CI 95%.")
    assert english["numbers"] <= korean["numbers"]


def test_numeric_magnitude_keeps_a_unit_difference_visible() -> None:
    assert "100ms" in tokens("# Test\n\n100 ms")["numbers"]
    assert "100ms" not in tokens("# 검증\n\n100초")["numbers"]


def test_source_only_scholarly_references_are_flagged() -> None:
    english = tokens("# Reference\n\n[Paper](https://aclanthology.org/2025.findings-acl.1258/)")
    korean = tokens("# 출처\n\n참고 문헌을 확인하십시오.")
    assert english["source_links"] - korean["source_links"] == {
        "https://aclanthology.org/2025.findings-acl.1258/"
    }


def test_language_specific_navigation_links_do_not_count_as_scholarly_loss() -> None:
    english = tokens('# Info\n\n[README](https://github.com/org/repo#readme)')
    korean = tokens('# 정보\n\n[한국어 README](https://github.com/org/repo/blob/main/README.ko.md)')
    assert english['source_links'] == korean['source_links'] == set()
