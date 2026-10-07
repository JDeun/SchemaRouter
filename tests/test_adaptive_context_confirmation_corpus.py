from scripts.generate_adaptive_context_confirmation_corpus import build_corpus


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
    assert len(corpus["tasks_sha256"]) == 64
