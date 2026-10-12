"""Regression contract for avoiding superseded bilingual GitHub Actions jobs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bilingual_repository_checks_cancel_only_superseded_pr_runs() -> None:
    for filename, prefix in (
        ("repository-facts.yml", "repository-facts"),
        ("korean-translation-coverage.yml", "korean-translation-coverage"),
    ):
        workflow = (ROOT / ".github/workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "concurrency:\n" in workflow
        assert (
            "  group: "
            + prefix
            + "-${{ github.event.pull_request.number || github.ref }}"
        ) in workflow
        assert (
            "  cancel-in-progress: "
            "${{ github.event_name == 'pull_request' }}"
        ) in workflow


def test_frozen_research_recovery_workflow_is_not_changed_by_ci_deduplication() -> None:
    workflow = (
        ROOT / ".github/workflows/research-0.14-heldout-recovery.yml"
    ).read_text(encoding="utf-8")
    assert "cancel-in-progress: false" in workflow
