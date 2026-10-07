import json
from pathlib import Path

from scripts.generate_adaptive_context_confirmation_corpus import build_corpus

CORPUS = Path("benchmarks/adaptive-context-confirmation-v1/corpus.json")


def test_confirmation_corpus_contract() -> None:
    corpus = build_corpus()
    tasks = corpus["tasks"]
    assert corpus["status"] == "frozen_unscored"
    assert corpus["task_count"] == 120
    assert set(corpus["languages"]) == {"en", "ko"}
    assert {task["kind"] for task in tasks} == {
        "single",
        "multi",
        "near_unsupported",
        "ood_unsupported",
    }
    assert sum(task["supported"] for task in tasks) == 60
    assert sum(not task["supported"] for task in tasks) == 60
    assert len({task["query"] for task in tasks}) == 120
    assert corpus["tasks_sha256"] == (
        "35911573c0d43a023cc9659fa3167a1c8870344701ec61fbccba6f3953c14707"
    )


def test_committed_confirmation_corpus_is_exact_generator_output() -> None:
    committed = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert committed == build_corpus()
