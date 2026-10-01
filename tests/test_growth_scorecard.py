from scripts.capture_growth_scorecard import render_markdown


def test_growth_scorecard_markdown_renders_available_and_unavailable_sources() -> None:
    scorecard = {
        "generated_at": "2026-10-01T00:00:00+00:00",
        "github": {
            "stars": 1,
            "forks": 0,
            "subscribers": 1,
            "open_issues": 26,
        },
        "pypi": {
            "status": "available",
            "last_day": 10,
            "last_week": 50,
            "last_month": 100,
        },
        "traffic": {
            "views_14d": {
                "status": "available",
                "data": {"count": 30, "uniques": 12},
            },
            "clones_14d": {
                "status": "unavailable",
                "error": "HTTP 403",
            },
        },
        "limitations": [
            "PyPI downloads are installation signals, not unique users.",
        ],
    }

    rendered = render_markdown(scorecard)

    assert "| GitHub stars | 1 | lagging |" in rendered
    assert "| PyPI downloads / month | 100 | leading |" in rendered
    assert "| GitHub views / 14d | 30 total / 12 unique | leading |" in rendered
    assert "unavailable (HTTP 403)" in rendered
    assert "not unique users" in rendered
