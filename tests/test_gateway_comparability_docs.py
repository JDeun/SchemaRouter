"""Regression checks for fair identity-conditioned gateway comparisons."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "docs/research/external-validation-freeze.md"
KO = ROOT / "docs_ko/research/external-validation-freeze.md"
UPSTREAM_RESPONSE = (
    "https://github.com/MikkoParkkola/mcp-gateway/issues/2641"
    "#issuecomment-5956919228"
)
UPSTREAM_CLOSURE = (
    "https://github.com/MikkoParkkola/mcp-gateway/issues/2641"
    "#issuecomment-6053555230"
)


def test_gateway_comparison_respects_native_authorization_and_interfaces() -> None:
    en = EN.read_text(encoding="utf-8")
    ko = KO.read_text(encoding="utf-8")
    for page in (en, ko):
        assert UPSTREAM_RESPONSE in page
        assert UPSTREAM_CLOSURE in page
        assert "mcp-gateway" in page
        assert "SchemaRouter" in page
        assert "4.0.0" in page
        assert "0.14" in page
    assert "Caller-conditioned candidate universe" in en
    assert "Native input evidence" in en
    assert "Measurement boundaries" in en
    assert "Native ranking concerns" in en
    assert "신원·권한별 후보 집합" in ko
    assert "시스템 고유 입력 근거" in ko
    assert "측정 경계" in ko
    assert "고유 순위 기준" in ko
    assert "No combined winner score" in en
    assert "공통 승자 점수" in ko
