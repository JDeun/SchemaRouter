from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "research-0.14-b2-smollm3-full.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_b2_resource_telemetry_is_observability_only() -> None:
    text = _workflow()

    assert "max-parallel: 4" in text
    assert "timeout-minutes: 45" in text
    assert 'matrix: "${{ fromJSON(needs.authorize.outputs.matrix) }}"' in text
    assert "continue-on-error: true" not in text

    assert "=== B2 runner resource baseline ===" in text
    assert "=== B2 resource telemetry ===" in text
    assert "free -m || true" in text
    assert "memory.current" in text
    assert "memory.max" in text
    assert "ps -eo pid,ppid,rss,vsz,pcpu,pmem,etime,comm --sort=-rss" in text
    assert "sleep 60" in text
    assert "/usr/bin/time -v python -u scripts/evaluate_agent_utility_phase_b_smollm3.py" in text


def test_b2_resource_telemetry_preserves_frozen_evaluator_arguments() -> None:
    text = _workflow()

    assert '--catalog-sizes "${{ matrix.catalog_sizes }}"' in text
    assert '--task-ids "${{ matrix.task_id }}"' in text
    assert '--out "artifacts/b2-shard/phase-b2-${{ matrix.job_id }}.json"' in text

    assert 'EXPECTED_EPISODES: "${{ matrix.expected_episodes }}"' in text
    assert 'EXPECTED_TASK_ID: "${{ matrix.task_id }}"' in text
    assert 'EXPECTED_CONDITIONS: "${{ matrix.conditions }}"' in text
    assert '--conditions "${{ matrix.conditions }}"' in text
    assert "agent-utility-v1-b2-sharding-runner-hardened.json" in text
