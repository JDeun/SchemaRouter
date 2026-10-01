from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Facts:
    stable_version: str
    release_date: str
    experiment_count: int
    development_version: str


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def load_facts() -> Facts:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    releases = re.findall(
        r"^## (\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2})$",
        changelog,
        flags=re.MULTILINE,
    )
    if not releases:
        raise RuntimeError("CHANGELOG.md has no stable release headings")
    stable_version, release_date = max(releases, key=lambda item: _version_key(item[0]))

    ledger = json.loads(
        (ROOT / "benchmarks" / "research-experiment-ledger.json").read_text(
            encoding="utf-8"
        )
    )
    experiments = ledger.get("experiments")
    if not isinstance(experiments, list):
        raise RuntimeError("research ledger experiments must be a list")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_block = re.search(
        r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)",
        pyproject,
    )
    if project_block is None:
        raise RuntimeError("pyproject.toml has no [project] table")
    version_match = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"\s*$',
        project_block.group(1),
    )
    if version_match is None:
        raise RuntimeError("pyproject.toml [project] table has no version")
    development_version = version_match.group(1)

    return Facts(
        stable_version=stable_version,
        release_date=release_date,
        experiment_count=len(experiments),
        development_version=development_version,
    )


def _replace(path: str, pattern: str, replacement: str, *, count: int = 1) -> None:
    file_path = ROOT / path
    text = file_path.read_text(encoding="utf-8")
    updated, replaced = re.subn(pattern, replacement, text, count=count, flags=re.MULTILINE)
    if replaced != count:
        raise RuntimeError(
            f"{path}: expected {count} match(es) for {pattern!r}, found {replaced}"
        )
    if updated != text:
        file_path.write_text(updated, encoding="utf-8")


def sync(facts: Facts) -> None:
    version = facts.stable_version
    date = facts.release_date
    count = facts.experiment_count

    # Repository landing pages.
    _replace(
        "README.md",
        r"(?m)^> \*\*Stable release: [^*]+\*\* · Beta / pre-1\.0$",
        f"> **Stable release: {version}** · Beta / pre-1.0",
    )
    _replace(
        "README.md",
        r"SchemaRouter `\d+\.\d+\.\d+` is \*\*Beta / pre-1\.0\*\*\.",
        f"SchemaRouter `{version}` is **Beta / pre-1.0**.",
    )
    _replace(
        "README.md",
        r"cacheSeconds=300&v=\d+\.\d+\.\d+",
        f"cacheSeconds=300&v={version}",
    )

    _replace(
        "README.ko.md",
        r"(?m)^> \*\*현재 안정판: [^*]+\*\* · Beta / pre-1\.0$",
        f"> **현재 안정판: {version}** · Beta / pre-1.0",
    )
    _replace(
        "README.ko.md",
        r"SchemaRouter `\d+\.\d+\.\d+`은 \*\*Beta / pre-1\.0\*\*입니다\.",
        f"SchemaRouter `{version}`은 **Beta / pre-1.0**입니다.",
    )
    _replace(
        "README.ko.md",
        r"cacheSeconds=300&v=\d+\.\d+\.\d+",
        f"cacheSeconds=300&v={version}",
    )

    _replace(
        "docs/index.md",
        r'<span class="sr-kicker">SchemaRouter \d+\.\d+\.\d+</span>',
        f'<span class="sr-kicker">SchemaRouter {version}</span>',
    )
    _replace(
        "docs_ko/index.md",
        r'<span class="sr-kicker">SchemaRouter \d+\.\d+\.\d+</span>',
        f'<span class="sr-kicker">SchemaRouter {version}</span>',
    )
    _replace(
        "docs_ko/index.md",
        r"현재 안정판은 \*\*\d+\.\d+\.\d+ \(Beta / pre-1\.0\)\*\* 입니다\.",
        f"현재 안정판은 **{version} (Beta / pre-1.0)** 입니다.",
    )

    # Install/status pages: only status facts, not release-specific prose.
    _replace(
        "docs/getting-started/installation.md",
        r"The current public release is `\d+\.\d+\.\d+`:",
        f"The current public release is `{version}`:",
    )
    _replace(
        "docs/getting-started/installation.md",
        (
            r"The published release tag and package metadata identify "
            r"`\d+\.\d+\.\d+` as the current non-prerelease"
        ),
        (
            f"The published release tag and package metadata identify `{version}` "
            "as the current non-prerelease"
        ),
    )
    _replace(
        "docs_ko/getting-started/installation.md",
        r"현재 공개 안정판은 `\d+\.\d+\.\d+`입니다\.",
        f"현재 공개 안정판은 `{version}`입니다.",
    )
    _replace(
        "docs_ko/getting-started/installation.md",
        r"공개 release tag와 package metadata에서 현재 정식 배포 버전은 `\d+\.\d+\.\d+`입니다\.",
        f"공개 release tag와 package metadata에서 현재 정식 배포 버전은 `{version}`입니다.",
    )

    # Stable trust index.
    _replace(
        "docs/project/trust-and-evidence.md",
        r"(?m)^\| Stable version \| `\d+\.\d+\.\d+` \|$",
        f"| Stable version | `{version}` |",
    )
    _replace(
        "docs/project/trust-and-evidence.md",
        r"(?m)^\| Release date \| \d{4}-\d{2}-\d{2} \|$",
        f"| Release date | {date} |",
    )
    _replace(
        "docs_ko/project/trust-and-evidence.md",
        r"(?m)^\| 안정판 \| `\d+\.\d+\.\d+` \|$",
        f"| 안정판 | `{version}` |",
    )
    _replace(
        "docs_ko/project/trust-and-evidence.md",
        r"(?m)^\| 릴리스 날짜 \| \d{4}-\d{2}-\d{2} \|$",
        f"| 릴리스 날짜 | {date} |",
    )

    # Research ledger counts are derived, never hand-maintained.
    _replace(
        "docs/research/experiment-index.md",
        r"independent experiment records: \d+;",
        f"independent experiment records: {count};",
    )
    _replace(
        "docs/research/experiment-index.md",
        r"The \d+-record count includes",
        f"The {count}-record count includes",
    )
    _replace(
        "docs/research/routing-status.md",
        r"all \d+ machine-readable experiment records;",
        f"all {count} machine-readable experiment records;",
    )


def check(facts: Facts) -> None:
    tracked = [
        "README.md",
        "README.ko.md",
        "docs/index.md",
        "docs_ko/index.md",
        "docs/getting-started/installation.md",
        "docs_ko/getting-started/installation.md",
        "docs/project/trust-and-evidence.md",
        "docs_ko/project/trust-and-evidence.md",
        "docs/research/experiment-index.md",
        "docs/research/routing-status.md",
    ]
    before = {path: (ROOT / path).read_bytes() for path in tracked}
    sync(facts)
    changed = [path for path in tracked if (ROOT / path).read_bytes() != before[path]]
    for path, content in before.items():
        (ROOT / path).write_bytes(content)

    if changed:
        joined = "\n- ".join(changed)
        raise SystemExit(
            "repository facts are stale. Run "
            "'python scripts/sync_repository_facts.py --write' and review the result:\n- "
            + joined
        )

    release_notes = ROOT / "docs" / "releases" / f"{facts.stable_version}.md"
    if not release_notes.is_file():
        raise SystemExit(f"missing stable release notes: {release_notes}")

    version = facts.development_version
    if ".dev" in version:
        base = version.removesuffix(".dev0")
        if version != f"{base}.dev0":
            raise SystemExit(f"development version must end in .dev0: {version}")
        if _version_key(base) <= _version_key(facts.stable_version):
            raise SystemExit(
                f"development version {version} must be newer than stable {facts.stable_version}"
            )
    elif version != facts.stable_version:
        raise SystemExit(
            f"release-state pyproject version {version} must match latest stable "
            f"changelog version {facts.stable_version}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize/check mechanical repository facts derived from canonical sources."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    facts = load_facts()
    if args.write:
        sync(facts)
        print(
            f"stable={facts.stable_version} release_date={facts.release_date} "
            f"experiments={facts.experiment_count} dev={facts.development_version}"
        )
    else:
        check(facts)
        print(
            f"repository facts OK: stable={facts.stable_version}, "
            f"experiments={facts.experiment_count}, dev={facts.development_version}"
        )


if __name__ == "__main__":
    main()
