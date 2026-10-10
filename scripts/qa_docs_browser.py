#!/usr/bin/env python3
"""Headless Chromium smoke for all built EN/KO pages and both language routes.

Run after strict MkDocs builds with Playwright Chromium installed:
  python scripts/qa_docs_browser.py site
  python scripts/qa_docs_browser.py --base-url https://jdeun.github.io/SchemaRouter/ --smoke-only

This checks actual CSS/DOM and browser navigation. It cannot certify translation meaning.
"""

from __future__ import annotations

import argparse
import functools
import re
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SAMPLES = (
    "",
    "getting-started/quickstart/",
    "reference/api/",
    "reference/runtime/",
    "research/design-and-experiment-history/",
    "research/typed-capability-retrieval-ablation/",
    "guides/mcp/",
    "project/roadmap/",
)
ANCHOR = "real-provider-capability"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _serve(site: Path) -> tuple[str, ThreadingHTTPServer, tempfile.TemporaryDirectory[str]]:
    temp = tempfile.TemporaryDirectory(prefix="schemarouter-qa-")
    (Path(temp.name) / "SchemaRouter").symlink_to(site.resolve(), target_is_directory=True)
    handler = functools.partial(QuietHandler, directory=temp.name)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/SchemaRouter/", server, temp


def _paths(site: Path) -> list[str]:
    paths = []
    for file in site.rglob("index.html"):
        rel = file.relative_to(site).as_posix().removesuffix("index.html")
        paths.append(rel)
    return sorted(paths)


def _switch(page: object, target_lang: str, expected: str) -> None:
    selector = f'a[hreflang="{target_lang}"]'
    locator = page.locator(selector).first
    assert locator.count(), f"missing language control: {selector} at {page.url}"
    locator.evaluate("(el) => el.click()")
    page.wait_for_url(expected, wait_until="domcontentloaded", timeout=20000)
    assert page.url == expected, (page.url, expected)


def _check_page(page: object, url: str) -> None:
    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    assert response and response.status == 200, (url, response.status if response else None)
    report = page.evaluate("""() => {
      const article = document.querySelector('article.md-content__inner');
      if (!article) return { error: 'article missing' };
      const h1 = article.querySelector('h1');
      const text = article.innerText.trim();
      const style = window.getComputedStyle(article);
      const titleStyle = h1 && window.getComputedStyle(h1);
      return {
        visible: article.getBoundingClientRect().width > 0 && style.display !== 'none',
        h1: Boolean(h1 && h1.innerText.trim()),
        chars: text.length,
        bodyPx: parseFloat(style.fontSize),
        titlePx: titleStyle ? parseFloat(titleStyle.fontSize) : 0
      };
    }""")
    assert "error" not in report, (url, report)
    assert report["visible"] and report["h1"] and report["chars"] >= 12, (url, report)
    assert report["bodyPx"] > 8 and report["titlePx"] > report["bodyPx"], (url, report)


def run(site: Path | None, base_url: str, smoke_only: bool, shots: Path | None) -> None:
    from playwright.sync_api import sync_playwright

    base_url = base_url.rstrip("/") + "/"
    pages = [lang + sample for sample in SAMPLES for lang in ("", "ko/")]
    if site and not smoke_only:
        pages = _paths(site)
        assert len(pages) >= 294, f"expected at least 147 complete EN/KO pairs; got {len(pages)}"
    errors: list[str] = []
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        checked = 0
        for rel in pages:
            checked += 1
            url = base_url + rel
            try:
                _check_page(page, url)
                if shots and rel in {"", "ko/", "getting-started/quickstart/",
                                      "ko/getting-started/quickstart/", "reference/api/",
                                      "ko/reference/api/",
                                      "research/design-and-experiment-history/",
                                      "ko/research/design-and-experiment-history/"}:
                    shots.mkdir(parents=True, exist_ok=True)
                    name = (rel.replace("/", "_") or "en-home") + ".png"
                    page.screenshot(path=str(shots / name), full_page=False)
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
                if len(errors) >= 30:
                    break
        print(f"browser pages attempted: {checked} / {len(pages)}")

        # Deep route with both search and fragment must survive EN->KO->EN.
        english = base_url + "getting-started/quickstart/?browser_qa=1#" + ANCHOR
        korean = base_url + "ko/getting-started/quickstart/?browser_qa=1#" + ANCHOR
        try:
            _check_page(page, english)
            _switch(page, "ko", korean)
            _switch(page, "en", english)
            print("bidirectional EN/KO query+fragment route preservation: OK")
        except Exception as exc:
            errors.append(f"language route preservation: {exc}")

        # HEAD 404 must route safely to language root, not a broken deep link.
        def reject_head(route: object) -> None:
            if route.request.method == "HEAD":
                route.fulfill(status=404)
            else:
                route.continue_()

        try:
            page.route(re.compile(r"/SchemaRouter/ko/getting-started/quickstart/"), reject_head)
            page.goto(base_url + "guides/mcp/", wait_until="domcontentloaded", timeout=30000)
            _check_page(page, english)
            _switch(page, "ko", base_url + "ko/?browser_qa=1")
            print("missing counterpart graceful language-root fallback: OK")
        except Exception as exc:
            errors.append(f"missing counterpart fallback: {exc}")
        finally:
            page.unroute(re.compile(r"/SchemaRouter/ko/getting-started/quickstart/"))
        context.close()
        browser.close()
    if errors:
        for error in errors:
            print("FAIL:", error)
        raise SystemExit(f"{len(errors)} browser QA failures")
    print(f"Chromium documentation QA OK: {len(pages)} pages + EN/KO routes + missing counterpart")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path, nargs="?")
    parser.add_argument("--base-url")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if not args.site and not args.base_url:
        parser.error("provide a built site directory or --base-url")
    if args.site and not args.site.is_dir():
        parser.error(f"site directory missing: {args.site}")
    if args.base_url:
        run(args.site, args.base_url, args.smoke_only, args.screenshots)
        return
    assert args.site is not None
    base, server, temp = _serve(args.site)
    try:
        run(args.site, base, args.smoke_only, args.screenshots)
    finally:
        server.shutdown()
        server.server_close()
        temp.cleanup()


if __name__ == "__main__":
    main()
