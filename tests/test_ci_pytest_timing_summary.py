"""Hermetic tests for the informational Python CI JUnit timing report."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci_pytest_timing_summary import render_timing_summary


def test_timing_report_ranks_slowest_tests_and_modules(tmp_path: Path) -> None:
    xml = tmp_path / "core.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3">
    <testcase classname="tests.unit" file="tests/test_unit.py" name="fast[0]" time="0.15" />
    <testcase classname="tests.slow" file="tests/test_slow.py" name="slow[1]" time="91.5" />
    <testcase classname="tests.slow" file="tests/test_slow.py" name="slow[2]" time="9.5" />
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )
    summary = render_timing_summary(xml, count=2)
    assert "Captured **3** pytest case timings" in summary
    assert summary.index("slow[1]") < summary.index("slow[2]")
    assert "| `tests/test_slow.py` | 101.00 |" in summary
    assert "| `tests/test_unit.py` |" not in summary


def test_timing_report_missing_xml_is_explicit_non_qualification(
    tmp_path: Path,
) -> None:
    summary = render_timing_summary(tmp_path / "not-created.xml")
    assert "were not produced" in summary
    assert "No runtime or coverage result can be inferred" in summary


def test_timing_report_escapes_parameterized_pytest_ids(
    tmp_path: Path,
) -> None:
    xml = tmp_path / "core.xml"
    xml.write_text(
        '<testsuite><testcase classname="x" name="abc|def" time="2.0"/></testsuite>',
        encoding="utf-8",
    )
    assert "abc\\|def" in render_timing_summary(xml)


def test_timing_report_rejects_non_positive_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        render_timing_summary(tmp_path / "core.xml", count=0)
