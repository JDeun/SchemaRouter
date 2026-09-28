from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def test_benchmark_cli_exposes_decision_plugin_options() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--decision-plugin" in completed.stdout
    assert "--decision-plugin-config-env" in completed.stdout


def test_plugin_runtime_metadata_omits_config_values() -> None:
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "benchmark_decision_routing",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load benchmark_decision_routing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = module._decision_plugin_runtime_metadata(
        plugin_name="anyjev",
        config_env="SCHEMAROUTER_DECISION_PLUGIN_CONFIG",
        config={
            "model": "example/model",
            "api_key": "super-secret-value",
        },
        plugin_info=SimpleNamespace(
            distribution="schemarouter-anyjev",
            version="1.2.3",
        ),
    )

    assert metadata == {
        "enabled": True,
        "name": "anyjev",
        "config_env": "SCHEMAROUTER_DECISION_PLUGIN_CONFIG",
        "config_keys": ["api_key", "model"],
        "distribution": "schemarouter-anyjev",
        "version": "1.2.3",
    }
    assert "super-secret-value" not in repr(metadata)
