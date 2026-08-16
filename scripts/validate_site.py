#!/usr/bin/env python3
"""Validate the static GitHub Pages layer without third-party dependencies."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []
        self.headings: list[int] = []
        self.report_cards = 0
        self.industry_links = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
            if "industry-research/" in values["href"]:
                self.industry_links += 1
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.styles.append(values["href"])
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "article" and "report-card" in (values.get("class") or "").split():
            self.report_cards += 1


def local_path(reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc or reference.startswith("#"):
        return None
    path = parsed.path.removeprefix("./").lstrip("/")
    if not path:
        return DOCS / "index.html"
    return DOCS / path


def main() -> None:
    required = [
        DOCS / "index.html",
        DOCS / "styles.css",
        DOCS / "app.js",
        DOCS / "favicon.svg",
        DOCS / "robots.txt",
        DOCS / "sitemap.xml",
        DOCS / ".nojekyll",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing site files: {', '.join(missing)}"

    parser = SiteParser()
    parser.feed((DOCS / "index.html").read_text(encoding="utf-8"))

    assert len(parser.ids) == len(set(parser.ids)), "Duplicate HTML IDs found"
    assert parser.headings and parser.headings[0] == 1, "The first heading must be H1"
    assert parser.headings.count(1) == 1, "The page must contain exactly one H1"
    assert parser.report_cards == 14, f"Expected 14 report cards, found {parser.report_cards}"
    assert parser.industry_links == 5, f"Expected 5 industry collections, found {parser.industry_links}"

    for reference in parser.links + parser.scripts + parser.styles:
        parsed = urlparse(reference)
        assert parsed.scheme != "http", f"Insecure URL: {reference}"
        path = local_path(reference)
        if path is not None:
            assert path.exists(), f"Missing local target: {reference}"

    javascript = (DOCS / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in javascript, "Avoid HTML injection in site JavaScript"

    print(
        "Site validation passed: "
        f"{parser.report_cards} report cards, "
        f"{parser.industry_links} industry collections, "
        f"{len(parser.links)} links"
    )


if __name__ == "__main__":
    main()
