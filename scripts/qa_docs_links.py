#!/usr/bin/env python3
"""Check every generated documentation link and local asset, not only headings.

Usage: python scripts/qa_docs_links.py site
This is a deterministic build-output check. External host health is out of scope.
"""

from __future__ import annotations

import argparse
import posixpath
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

PREFIX = "/SchemaRouter/"
SKIP_SCHEMES = {"mailto", "tel", "data", "javascript", "blob"}


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        props = dict(attrs)
        if props.get("id"):
            self.ids.add(props["id"])
        attribute = "href" if tag == "a" else "src" if tag in {"img", "iframe", "source"} else None
        if attribute and props.get(attribute):
            self.links.append((tag, props[attribute]))


def resolve(site: Path, source: Path, url: str) -> tuple[Path, str] | None:
    parsed = urlsplit(url)
    if parsed.scheme in SKIP_SCHEMES:
        return None
    if parsed.scheme not in {"", "http", "https"} or parsed.netloc:
        # The public pages use site-relative links. Do not probe unrelated sites.
        return None
    if url.startswith("//"):
        return None
    if parsed.path.startswith("/"):
        if not parsed.path.startswith(PREFIX):
            # Links to elsewhere on the same domain are not documentation files.
            return None
        rel = parsed.path[len(PREFIX):]
    elif parsed.path:
        rel = posixpath.join(source.parent.relative_to(site).as_posix(), parsed.path)
    else:
        rel = source.relative_to(site).as_posix()
    rel = posixpath.normpath(unquote(rel))
    if rel == ".." or rel.startswith("../"):
        raise ValueError("relative target escapes docs root")
    target = site / rel
    if target.is_dir() or parsed.path.endswith("/") or not target.suffix:
        target /= "index.html"
    return target, unquote(parsed.fragment)


def inspect(site: Path) -> tuple[list[str], Counter[str]]:
    site = site.resolve()
    pages = sorted(site.rglob("*.html"))
    parsed: dict[Path, Links] = {}
    for page in pages:
        obj = Links()
        obj.feed(page.read_text(encoding="utf-8"))
        parsed[page] = obj

    counts: Counter[str] = Counter()
    errors: list[str] = []
    for source, page in parsed.items():
        for tag, link in page.links:
            counts["local_link_candidates"] += 1
            try:
                dest = resolve(site, source, link)
            except ValueError as exc:
                errors.append(f"{source.relative_to(site)}: {link!r}: {exc}")
                continue
            if dest is None:
                counts["external_or_ignored"] += 1
                continue
            target, fragment = dest
            counts["checked_local"] += 1
            if not target.is_file():
                errors.append(f"{source.relative_to(site)}: missing {tag} target {link!r}")
                continue
            if fragment and target.suffix == ".html":
                target_page = parsed.get(target)
                if target_page is None:
                    target_page = Links()
                    target_page.feed(target.read_text(encoding="utf-8"))
                    parsed[target] = target_page
                if fragment not in target_page.ids:
                    errors.append(f"{source.relative_to(site)}: missing anchor {link!r}")
                else:
                    counts["checked_anchors"] += 1
    counts["html_pages"] = len(pages)
    return errors, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    errors, counts = inspect(args.site)
    for name, value in sorted(counts.items()):
        print(f"{name}: {value}")
    if errors:
        for error in errors[:100]:
            print("FAIL:", error)
        raise SystemExit(f"{len(errors)} broken local documentation links/assets")
    print("Every local rendered documentation link and asset resolves")


if __name__ == "__main__":
    main()
