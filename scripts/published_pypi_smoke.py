from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from compatibility_report import new_report, write_report
from pydantic import BaseModel

from schemarouter import PlanRequest, SchemaRouter, __version__, schema_tool


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    """Return a deterministic value for the published-package smoke."""
    return Weather(city=city, temperature=20.5)


def run_smoke() -> dict[str, object]:
    distribution_version = version("schemarouter")
    assert distribution_version == __version__
    assert ".dev" not in distribution_version

    router = SchemaRouter()
    key = router.add_callable(current_weather)
    results = router.invoke(
        PlanRequest(
            query="city temperature",
            preferred_tools=[key],
            arguments={"city": "Seoul"},
        )
    )

    assert len(results) == 1
    assert results[0].tool == key
    assert results[0].endpoint == "call"
    assert results[0].data == {"city": "Seoul", "temperature": 20.5}

    return {
        "distribution": "schemarouter",
        "version": distribution_version,
        "tool": key,
        "endpoint": results[0].endpoint,
        "result": results[0].data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test the installed stable SchemaRouter distribution from PyPI."
    )
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--artifact-kind", choices=("wheel", "sdist"), default="wheel")
    args = parser.parse_args()

    report = new_report(
        adapter="published-package",
        source=f"PyPI latest stable {args.artifact_kind}",
    )
    try:
        report["details"] = run_smoke()
        report["artifact_kind"] = args.artifact_kind
        report["status"] = "success"
    except Exception as exc:
        report["artifact_kind"] = args.artifact_kind
        report["status"] = "failure"
        report["error_type"] = type(exc).__name__
        write_report(args.json_out, report)
        raise

    write_report(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
