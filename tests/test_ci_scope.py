import re
from pathlib import Path

from scripts.ci_scope import classify_paths


def test_ci_scope_core_runtime_change_is_not_full_fanout() -> None:
    scopes = classify_paths(["src/schemarouter/runtime.py"])

    assert scopes["package"] is True
    assert scopes["runtime"] is True
    assert scopes["full"] is False
    assert scopes["pydanticai"] is False
    assert scopes["docs"] is False


def test_ci_scope_native_adapter_targets_native_qualification() -> None:
    scopes = classify_paths(["src/schemarouter/adapters/vector_native.py"])

    assert scopes["native"] is True
    assert scopes["package"] is True
    assert scopes["database"] is False


def test_ci_scope_docs_only_does_not_request_package_qualification() -> None:
    scopes = classify_paths(["docs/guides/runtime.md"])

    assert scopes["docs"] is True
    assert scopes["package"] is False
    assert scopes["runtime"] is False


def test_ci_scope_dependency_change_expands_optional_integration_surface() -> None:
    scopes = classify_paths(["pyproject.toml"])

    assert scopes["deps"] is True
    assert scopes["package"] is True
    assert scopes["langchain"] is True
    assert scopes["llamaindex"] is True
    assert scopes["mcp"] is True
    assert scopes["database"] is True


def test_ci_scope_ci_definition_change_requests_full_qualification() -> None:
    scopes = classify_paths([".github/workflows/ci.yml"])

    assert all(scopes.values())


def test_protected_required_contexts_never_use_job_level_path_skips() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    protected_scoped_jobs = (
        "test-311-scheduled",
        "test-313-scheduled",
        "minimum-dependencies",
        "langchain-integration",
        "llamaindex-integration",
        "jev-integration",
        "otel-integration",
        "mcp-integration",
        "docs",
    )

    for job_id in protected_scoped_jobs:
        marker = f"\n  {job_id}:\n"
        start = workflow.index(marker) + len(marker)
        remainder = workflow[start:]
        next_job = re.search(r"\n  [A-Za-z0-9_-]+:\n", remainder)
        block = remainder if next_job is None else remainder[: next_job.start()]

        # Protected rulesets do not accept these contexts when the whole job is
        # skipped. Path qualification therefore belongs on expensive steps, while
        # the required job itself must always reach a successful conclusion.
        assert "\n    if:" not in block, job_id



def test_core_python_workflows_cache_only_pip_downloads_with_complete_keys() -> None:
    workflows = (
        ".github/workflows/ci.yml",
        ".github/workflows/compatibility.yml",
        ".github/workflows/docs.yml",
        ".github/workflows/post-merge-qualification.yml",
        ".github/workflows/python-compatibility.yml",
        ".github/workflows/python-preview.yml",
        ".github/workflows/release.yml",
        ".github/workflows/retrieval-fast-path-validation.yml",
        ".github/workflows/security.yml",
    )

    for workflow_path in workflows:
        workflow = Path(workflow_path).read_text(encoding="utf-8")
        setup_steps = workflow.split("uses: actions/setup-python@")[1:]
        assert setup_steps, workflow_path

        for remainder in setup_steps:
            block = remainder.split("\n      -", 1)[0]
            assert "cache:" in block and "pip" in block, workflow_path
            assert "cache-dependency-path:" in block, workflow_path
            assert "pyproject.toml" in block, workflow_path
            assert workflow_path in block, workflow_path

        assert "site-packages" not in workflow
        assert ".venv" not in workflow
