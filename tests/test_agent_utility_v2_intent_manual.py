from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.generate_agent_utility_v2_dev import freeze_dev
from scripts.generate_agent_utility_v2_intent_manual import (
    GENERATOR_REVISION,
    generate_all,
)

ROOT = Path(__file__).resolve().parents[1]


def test_intent_manual_generation_is_deterministic_and_provenanced(
    tmp_path: Path,
) -> None:
    freeze_dir = tmp_path / "freeze"
    freeze_dev(freeze_dir)

    first = generate_all(freeze_dir, tmp_path / "first")
    second = generate_all(freeze_dir, tmp_path / "second")

    assert first == second
    assert first["surface"] == "development"
    assert first["confirmation_surface_opened"] is False
    assert first["generator_revision"] == GENERATOR_REVISION

    for size in ("100", "250", "500", "1000"):
        first_payload = json.loads(
            (tmp_path / "first" / f"intent-manual-{size}.json")
            .read_text(encoding="utf-8")
        )
        second_payload = json.loads(
            (tmp_path / "second" / f"intent-manual-{size}.json")
            .read_text(encoding="utf-8")
        )
        assert first_payload == second_payload
        assert first_payload["endpoint_count"] == int(size)
        assert len(first_payload["rows"]) == int(size)
        assert first_payload["source_catalog_sha256"] == (
            first["catalogs"][size]["source_catalog_sha256"]
        )

        route_ids = {row["route_id"] for row in first_payload["rows"]}
        assert len(route_ids) == int(size)
        for row in first_payload["rows"]:
            assert row["generator_revision"] == GENERATOR_REVISION
            assert len(row["tool_fingerprint"]) == 64
            assert len(row["endpoint_fingerprint"]) == 64
            assert 1 <= len(row["intents"]) <= 4
            assert len(
                {
                    intent["text"].strip().casefold()
                    for intent in row["intents"]
                }
            ) == len(row["intents"])


def test_intent_manual_confirmation_generation_fails_closed(
    tmp_path: Path,
) -> None:
    freeze_dir = tmp_path / "freeze"
    freeze_dev(freeze_dir)

    process = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "scripts"
                / "generate_agent_utility_v2_intent_manual.py"
            ),
            "--surface",
            "confirmation",
            "--freeze-dir",
            str(freeze_dir),
            "--out-dir",
            str(tmp_path / "forbidden"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode != 0
    assert "confirmation intent-manual generation is sealed" in (
        process.stdout + process.stderr
    )


def test_intent_manual_amendment_forbids_eval_and_b1_inputs() -> None:
    amendment = json.loads(
        (
            ROOT
            / "benchmarks"
            / "agent-utility-v2-intent-manual-amendment.json"
        ).read_text(encoding="utf-8")
    )

    forbidden = set(amendment["forbidden_inputs"])
    assert {
        "evaluation_queries",
        "gold_required_routes",
        "B1_rows",
        "B1_errors",
        "confirmation_rows",
        "retrieval_results",
        "retrieval_ranks",
    } <= forbidden
    assert amendment["evaluation"]["confirmation_allowed"] is False
    assert amendment["generator"]["type"] == "deterministic_template_no_llm"
