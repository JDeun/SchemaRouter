"""The actual pinned-Qwen CI run must exercise the approved G5 E1 arm."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/research-real-qwen-open-meteo-two-hop-e1.yml"
)


def test_pinned_model_job_runs_separate_documented_native_g5_comparison() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    # 기존 단독 E1 실험이 먼저 실행되어 같은 runner에 고정 Qwen 가중치가
    # 캐시된 후, 오프라인 강제 로딩 G5 비교가 실행되어야 합니다.
    original = workflow.index("--out artifacts/real-qwen-open-meteo-e1/report.json")
    paired = workflow.index("--compare-graph --documented-noncommercial-e1")
    assert original < paired
    assert "--out artifacts/real-qwen-open-meteo-g5-paired-e1/report.json" in workflow

    # 차단·소스 드리프트 결과에 성공률을 합성하지 않고 별도 기록합니다.
    assert '"REAL_QWEN_NATIVE_G5_PAIRED_E1_DEV"' in workflow
    assert '"E1_MEASURED_DEV_NOT_E2"' in workflow
    assert '"BLOCKED_MODEL_RUNTIME"' in workflow
    assert '"INCOMPARABLE_SOURCE_DRIFT"' in workflow
    assert '"INCOMPARABLE_SOURCE_FAILURE"' in workflow
    assert '"task_success_rate"' in workflow
    assert "Input tokens | Schema tokens | Output tokens" in workflow
    assert 'outcome["token_accounting_complete"]' in workflow
    assert "real-qwen-open-meteo-g5-paired-e1-${{ github.run_id }}" in workflow
    assert "artifacts/real-qwen-open-meteo-g5-paired-e1/report.json" in workflow

