#!/usr/bin/env python3
"""Prepare the Korean MkDocs tree without duplicating the canonical English docs.

English under docs/ is canonical. First-class Korean translations live under docs_ko/.
For every untranslated canonical Markdown page, this script emits a Korean placeholder
at the same relative URL that links back to the English original. That keeps Material's
language switcher page-stable without allowing translations to silently drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "docs"
TRANSLATION_DIR = ROOT / "docs_ko"
MANIFEST_PATH = TRANSLATION_DIR / "translation-manifest.json"
DEFAULT_OUTPUT = ROOT / ".build" / "docs-ko"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def canonical_url(relative: Path) -> str:
    path = relative.as_posix()
    if path == "index.md":
        return "https://jdeun.github.io/SchemaRouter/"
    if path.endswith("/index.md"):
        path = path[: -len("index.md")]
    elif path.endswith(".md"):
        path = path[:-3] + "/"
    return "https://jdeun.github.io/SchemaRouter/" + path


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load_manifest() -> dict[str, str]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise SystemExit("unsupported translation manifest schema")
    entries = raw.get("translations")
    if not isinstance(entries, list):
        raise SystemExit("translation manifest must contain a translations list")

    mapping: dict[str, str] = {}
    for entry in entries:
        path = entry.get("path")
        source_blob = entry.get("source_blob")
        if not isinstance(path, str) or not isinstance(source_blob, str):
            raise SystemExit(f"invalid translation manifest entry: {entry!r}")
        if path in mapping:
            raise SystemExit(f"duplicate translation manifest path: {path}")
        mapping[path] = source_blob
    return mapping


def validate_translations(manifest: dict[str, str]) -> None:
    translated_files = {
        path.relative_to(TRANSLATION_DIR).as_posix()
        for path in TRANSLATION_DIR.rglob("*.md")
    }
    manifested_files = set(manifest)

    extra = sorted(translated_files - manifested_files)
    missing = sorted(manifested_files - translated_files)
    if extra:
        raise SystemExit(
            "Korean translation files missing from translation-manifest.json: "
            + ", ".join(extra)
        )
    if missing:
        raise SystemExit(
            "translation-manifest.json entries missing translated files: "
            + ", ".join(missing)
        )

    stale: list[str] = []
    for relative, expected_blob in sorted(manifest.items()):
        source = CANONICAL_DIR / relative
        if not source.is_file():
            raise SystemExit(f"canonical source no longer exists: docs/{relative}")
        actual_blob = git_blob_sha(source.read_bytes())
        if actual_blob != expected_blob:
            stale.append(
                f"{relative}: expected {expected_blob}, canonical source is {actual_blob}"
            )

    if stale:
        raise SystemExit(
            "Korean translations are stale. Update the translation and its source_blob:\n- "
            + "\n- ".join(stale)
        )


def write_fallback(source: Path, destination: Path, relative: Path) -> None:
    title = first_heading(source.read_text(encoding="utf-8"), relative.stem)
    english_url = canonical_url(relative)
    content = f"""# {title}

!!! info "한국어 번역 준비 중"

    이 문서는 아직 한국어 전체 번역이 준비되지 않았습니다. 영어 원문은 계속 최신 상태로
    유지되며, 번역되지 않은 내용을 임의로 축약해서 제공하지 않습니다.

[영어 원문에서 이 문서 보기 →]({english_url})

[한국어 문서 홈으로 이동 →](https://jdeun.github.io/SchemaRouter/ko/)
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def prepare(output: Path) -> tuple[int, int]:
    manifest = load_manifest()
    validate_translations(manifest)

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    translated = 0
    fallbacks = 0
    for source in sorted(CANONICAL_DIR.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(CANONICAL_DIR)
        destination = output / relative

        if source.suffix.lower() != ".md":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            continue

        translation = TRANSLATION_DIR / relative
        if translation.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(translation, destination)
            translated += 1
        else:
            write_fallback(source, destination, relative)
            fallbacks += 1

    return translated, fallbacks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="staging docs directory for the Korean MkDocs build",
    )
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = ROOT / output

    translated, fallbacks = prepare(output)
    print(
        f"prepared Korean docs: {translated} translated pages, "
        f"{fallbacks} explicit English fallbacks -> {output}"
    )


if __name__ == "__main__":
    main()
