"""Summarize measured per-test JUnit durations from the protected Python 3.12 CI.

The report is informational: test selection, pass/fail, and core coverage
thresholds remain enforced by pytest and the existing coverage job.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


def _cell(value: str) -> str:
    """Escape user-defined pytest IDs in a GitHub Markdown table cell."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_timing_summary(path: Path, *, count: int = 25) -> str:
    if count < 1:
        raise ValueError("count must be positive")
    if not path.exists():
        return (
            "## Python 3.12 pytest timing diagnostics\n\n"
            "JUnit test timings were not produced (the test job may have been "
            "interrupted). No runtime or coverage result can be inferred.\n"
        )

    root = ET.parse(path).getroot()
    cases: list[tuple[str, float, str]] = []
    total_by_module: dict[str, float] = defaultdict(float)
    for case in root.iter("testcase"):
        name = case.get("name", "unknown")
        module = case.get("file") or case.get("classname") or "unknown"
        try:
            seconds = float(case.get("time", "0"))
        except ValueError:
            seconds = 0.0
        seconds = max(seconds, 0.0)
        cases.append((f"{module}::{name}", seconds, module))
        total_by_module[module] += seconds

    lines = [
        "## Python 3.12 pytest timing diagnostics",
        "",
        f"Captured **{len(cases)}** pytest case timings.",
        "Durations include pytest's per-case setup, call and teardown; "
        "module totals are additive case-time, not wall-clock or parallel CI time.",
        "",
        f"### Slowest {min(count, len(cases))} individual tests",
        "",
        "| Test node | Seconds |",
        "| --- | ---: |",
    ]
    for name, secs, _ in sorted(cases, key=lambda x: x[1], reverse=True)[:count]:
        lines.append(f"| \`{_cell(name)}\` | {secs:.2f} |")

    lines.extend([
        "",
        f"### Slowest {min(count, len(total_by_module))} modules (total test time)",
        "",
        "| Module | Seconds |",
        "| --- | ---: |",
    ])
    for module, secs in sorted(
        total_by_module.items(), key=lambda x: x[1], reverse=True
    )[:count]:
        lines.append(f"| \`{_cell(module)}\` | {secs:.2f} |")
    lines.extend([
        "",
        "The source JUnit XML artifact contains all recorded cases, including failures.",
        "This report does not waive the unchanged >=84% measured coverage floor.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()
    print(render_timing_summary(args.junit_xml, count=args.top))


if __name__ == "__main__":
    main()
