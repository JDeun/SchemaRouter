#!/usr/bin/env python3
"""Check rendered Pages HTML for code-block rendering failures."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path


class CodeBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.pre_stack: list[bool] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line = self.getpos()[0]
        if tag == "pre":
            if self.pre_stack:
                self.errors.append(f"line {line}: nested <pre> element")
            self.pre_stack.append(False)
        elif tag == "code" and self.pre_stack:
            self.pre_stack[-1] = True

    def handle_endtag(self, tag: str) -> None:
        line = self.getpos()[0]
        if tag != "pre":
            return
        if not self.pre_stack:
            self.errors.append(f"line {line}: closing </pre> without opening <pre>")
            return
        if not self.pre_stack.pop():
            self.errors.append(f"line {line}: rendered <pre> block contains no <code> element")


def check_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for marker in ("```", "~~~"):
        if marker in text:
            errors.append(f"raw Markdown fence {marker!r} survived into rendered HTML")
    parser = CodeBlockParser()
    parser.feed(text)
    parser.close()
    errors.extend(parser.errors)
    if parser.pre_stack:
        errors.append("unclosed <pre> element")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    html_files = sorted(args.site.rglob("*.html"))
    if not html_files:
        raise SystemExit(f"no rendered HTML found under {args.site}")
    failures: list[str] = []
    for path in html_files:
        for error in check_html(path):
            failures.append(f"{path}: {error}")
    if failures:
        raise SystemExit("rendered documentation structure check failed:\\n- " + "\\n- ".join(failures))
    print(f"rendered documentation structure OK: {len(html_files)} HTML files")


if __name__ == "__main__":
    main()
