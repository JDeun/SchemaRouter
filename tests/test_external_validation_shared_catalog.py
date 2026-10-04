from scripts.external_validation_shared_catalog import build_package


def test_shared_external_package_is_frozen_and_reproducible() -> None:
    package = build_package()
    assert package["schema_version"] == 1
    assert package["package_id"] == "gearlynx-shared-router-v1"
    assert len(package["catalog"]) == 82
    assert len(package["cases"]) == 16
    assert sum(case["label"] == "unsupported" for case in package["cases"]) == 4
    assert len(package["catalog_sha256"]) == 64
    assert len(package["cases_sha256"]) == 64
    assert package["budget"]["top_k"] == 3
    assert package["metrics"]["field_recall"] is False
    assert package["external_runner_contract"]["notes"][-1] == (
        "Report negative results unchanged."
    )
