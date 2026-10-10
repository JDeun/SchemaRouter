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


def test_security_critical_bilingual_datascope_contracts_remain_explicit() -> None:
    root = Path(__file__).resolve().parents[1] / "docs_ko" / "guides"
    graph = (root / "graph-store-onboarding.md").read_text(encoding="utf-8")
    vector = (root / "vector-store-onboarding.md").read_text(encoding="utf-8")
    inspection = (root / "inspection.md").read_text(encoding="utf-8")
    assert "ScopedGraphStoreBackend" in graph
    assert "supports_trusted_filters = True" in graph
    assert "이전에 fail-closed" in graph
    assert "지원한다고 주장하지 않습니다" in graph
    assert "ScopedVectorStoreBackend" in vector
    assert "supports_trusted_filters = True" in vector
    assert "tuple 값은" in vector
    assert "I/O 이전에 fail-closed" in vector
    assert "`router.inspect()` snapshot" in inspection
    assert "trace 저장소" in inspection


def test_korean_research_negative_evidence_and_stopping_rule_stay_explicit() -> None:
    root = Path(__file__).resolve().parents[1] / "docs_ko"
    history = (root / "research" / "design-and-experiment-history.md").read_text(
        encoding="utf-8"
    )
    routing = (root / "research" / "routing-status.md").read_text(
        encoding="utf-8"
    )
    release_04 = (root / "releases" / "0.4.0.md").read_text(encoding="utf-8")
    release_05 = (root / "releases" / "0.5.0.md").read_text(encoding="utf-8")

    # The diagnostic +27 is not an accepted scientific improvement.
    assert "1,019건" in history
    assert "**1,046건**" in history
    assert "진단용 상한일 뿐 확정된 개선 결과가 아닙니다" in history

    # Preserve preregistered stop decisions and veto-only execution authority.
    assert "사전 등록한 중단 규칙을 적용합니다" in history
    assert "결과 확인 후 추가하는 수작업 규칙" in history
    assert "**거부(veto) 전용**" in history
    assert "사후 수정하지 않습니다" in history
    assert "모델 품질이 낮다는 부정적 증거는 아닙니다" in history
    assert "계층형 온톨로지의 강제 필터링" in history

    # Do not promote an unscored confirmatory corpus into a result.
    assert "`not_entailment`" in routing
    assert "별도로 동결한 확인용 데이터셋은 아직 **채점하지 않았습니다**" in routing
    assert "The exact formulation is terminal" not in routing

    # Release notes must keep trusted hook and wall-clock safety semantics.
    assert "훅에서 발생한 실패는 재시도 대상이 아니며" in release_04
    assert "실제 경과 시간 한도를 초과해 계속 동작할 수 있었던 허점을" in release_05
