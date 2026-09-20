import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "assets" / "brand"


def _svg_root(name: str) -> ET.Element:
    path = BRAND / name
    assert path.exists(), f"missing brand asset: {path}"
    return ET.parse(path).getroot()


def test_brand_svg_assets_are_well_formed() -> None:
    expected = {
        "schemarouter-mark-light.svg",
        "schemarouter-mark-dark.svg",
        "schemarouter-lockup-light.svg",
        "schemarouter-lockup-dark.svg",
        "schemarouter-social-preview.svg",
    }

    assert expected.issubset({path.name for path in BRAND.glob("*.svg")})
    for name in expected:
        root = _svg_root(name)
        assert root.tag.endswith("svg")


def test_compact_marks_keep_square_viewbox() -> None:
    for name in (
        "schemarouter-mark-light.svg",
        "schemarouter-mark-dark.svg",
    ):
        root = _svg_root(name)
        assert root.attrib["viewBox"] == "0 0 512 512"


def test_lockups_keep_shared_canvas() -> None:
    for name in (
        "schemarouter-lockup-light.svg",
        "schemarouter-lockup-dark.svg",
    ):
        root = _svg_root(name)
        assert root.attrib["viewBox"] == "0 0 1200 360"


def test_social_preview_source_is_github_sized() -> None:
    root = _svg_root("schemarouter-social-preview.svg")
    assert root.attrib["width"] == "1280"
    assert root.attrib["height"] == "640"
    assert root.attrib["viewBox"] == "0 0 1280 640"


def test_readme_brand_assets_use_package_index_safe_urls() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    raw_base = "https://raw.githubusercontent.com/JDeun/SchemaRouter/main/"
    assert raw_base + "docs/assets/brand/schemarouter-lockup-light.svg" in readme
    assert raw_base + "docs/assets/brand/schemarouter-lockup-dark.svg" in readme


def test_mkdocs_references_production_brand_assets() -> None:
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "logo: assets/brand/schemarouter-mark-dark.svg" in config
    assert "favicon: assets/brand/schemarouter-mark-light.svg" in config
    assert "project/brand.md" in config
