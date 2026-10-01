from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _get_json(url: str, *, token: str | None = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SchemaRouter-growth-scorecard",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_source(
    name: str,
    url: str,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    try:
        return {
            "status": "available",
            "data": _get_json(url, token=token),
        }
    except HTTPError as exc:
        return {
            "status": "unavailable",
            "error": f"HTTP {exc.code}",
            "source": name,
        }
    except (URLError, TimeoutError, ValueError) as exc:
        return {
            "status": "unavailable",
            "error": type(exc).__name__,
            "source": name,
        }


def capture_scorecard(
    repository: str,
    package: str,
    *,
    github_token: str | None = None,
) -> dict[str, Any]:
    repo_url = f"https://api.github.com/repos/{repository}"
    repo_source = _safe_source("github_repository", repo_url, token=github_token)
    if repo_source["status"] != "available":
        raise RuntimeError(
            "GitHub repository metadata is required for a growth scorecard: "
            f"{repo_source.get('error', 'unknown error')}"
        )

    repo = repo_source["data"]
    github = {
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "subscribers": repo["subscribers_count"],
        "open_issues": repo["open_issues_count"],
        "network_count": repo["network_count"],
        "created_at": repo["created_at"],
        "pushed_at": repo["pushed_at"],
        "topics": repo.get("topics", []),
    }

    pypi = _safe_source(
        "pypistats_recent",
        f"https://pypistats.org/api/packages/{package}/recent",
    )
    if pypi["status"] == "available":
        pypi = {
            "status": "available",
            **pypi["data"]["data"],
        }

    traffic_token = github_token or None
    views = _safe_source(
        "github_traffic_views",
        f"{repo_url}/traffic/views",
        token=traffic_token,
    )
    clones = _safe_source(
        "github_traffic_clones",
        f"{repo_url}/traffic/clones",
        token=traffic_token,
    )

    traffic = {
        "views_14d": views,
        "clones_14d": clones,
        "note": (
            "GitHub traffic covers only the most recent 14 days and requires "
            "repository traffic permission. Missing permission is recorded, not fatal."
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "package": package,
        "github": github,
        "pypi": pypi,
        "traffic": traffic,
        "metric_classes": {
            "leading": [
                "pypi.last_day",
                "pypi.last_week",
                "pypi.last_month",
                "traffic.views_14d",
                "traffic.clones_14d",
            ],
            "lagging": [
                "github.stars",
                "github.forks",
                "github.subscribers",
                "external_adopters",
                "contributors",
            ],
        },
        "limitations": [
            "PyPI downloads are installation signals, not unique users.",
            "GitHub stars are a lagging awareness signal, not adoption.",
            "GitHub traffic is a rolling 14-day window and may be unavailable without permission.",
            "External adopters and downstream CI usage require separate evidence collection.",
            "SchemaRouter does not add product telemetry solely for growth analytics.",
        ],
    }


def _traffic_value(source: dict[str, Any], key: str) -> str:
    if source.get("status") != "available":
        return f"unavailable ({source.get('error', 'unknown')})"
    value = source.get("data", {}).get(key)
    uniques = source.get("data", {}).get("uniques")
    if value is None:
        return "unavailable"
    return f"{value} total / {uniques} unique"


def render_markdown(scorecard: dict[str, Any]) -> str:
    github = scorecard["github"]
    pypi = scorecard["pypi"]
    traffic = scorecard["traffic"]

    if pypi.get("status") == "available":
        pypi_day = str(pypi["last_day"])
        pypi_week = str(pypi["last_week"])
        pypi_month = str(pypi["last_month"])
    else:
        reason = pypi.get("error", "unknown")
        pypi_day = pypi_week = pypi_month = f"unavailable ({reason})"

    rows = [
        ("GitHub stars", github["stars"], "lagging"),
        ("GitHub forks", github["forks"], "lagging"),
        ("GitHub subscribers", github["subscribers"], "lagging"),
        ("Open issues + PRs", github["open_issues"], "operational"),
        ("PyPI downloads / day", pypi_day, "leading"),
        ("PyPI downloads / week", pypi_week, "leading"),
        ("PyPI downloads / month", pypi_month, "leading"),
        (
            "GitHub views / 14d",
            _traffic_value(traffic["views_14d"], "count"),
            "leading",
        ),
        (
            "GitHub clones / 14d",
            _traffic_value(traffic["clones_14d"], "count"),
            "leading",
        ),
    ]

    lines = [
        "# SchemaRouter adoption scorecard",
        "",
        f"Generated: {scorecard['generated_at']}",
        "",
        "| Metric | Value | Class |",
        "| --- | ---: | --- |",
    ]
    for metric, value, metric_class in rows:
        lines.append(f"| {metric} | {value} | {metric_class} |")

    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in scorecard["limitations"])
    lines.extend(
        [
            "",
            "External adopters, downstream CI use, and case studies are tracked separately because "
            "they cannot be inferred reliably from public package/repository counters.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="JDeun/SchemaRouter")
    parser.add_argument("--package", default="schemarouter")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args()

    scorecard = capture_scorecard(
        args.repository,
        args.package,
        github_token=os.environ.get("GITHUB_TOKEN"),
    )

    json_path = Path(args.json_out)
    markdown_path = Path(args.markdown_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(scorecard), encoding="utf-8")


if __name__ == "__main__":
    main()
