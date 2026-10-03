#!/usr/bin/env python3
"""Validate the static GitHub Pages layer without third-party dependencies."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPORT_INDEX = ROOT / "data" / "report-index.json"


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
        self.canonical: list[str] = []
        self.json_ld: list[str] = []
        self._json_ld_buffer: list[str] | None = None

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
        if tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonical.append(values["href"])
        if tag == "script" and values.get("type") == "application/ld+json":
            self._json_ld_buffer = []
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "article" and "report-card" in (values.get("class") or "").split():
            self.report_cards += 1

    def handle_data(self, data: str) -> None:
        if self._json_ld_buffer is not None:
            self._json_ld_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld_buffer is not None:
            self.json_ld.append("".join(self._json_ld_buffer))
            self._json_ld_buffer = None


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
        REPORT_INDEX,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing site files: {', '.join(missing)}"

    parser = SiteParser()
    parser.feed((DOCS / "index.html").read_text(encoding="utf-8"))

    assert len(parser.ids) == len(set(parser.ids)), "Duplicate HTML IDs found"
    assert parser.headings and parser.headings[0] == 1, "The first heading must be H1"
    assert parser.headings.count(1) == 1, "The page must contain exactly one H1"
    assert parser.report_cards == 19, f"Expected 19 report cards, found {parser.report_cards}"
    assert parser.industry_links == 5, f"Expected 5 industry collections, found {parser.industry_links}"
    assert parser.canonical == ["https://openfutureforum.github.io/executive-ai-research/"], "Unexpected canonical URL"
    assert parser.json_ld, "JSON-LD is required"
    json_ld_documents = [json.loads(block) for block in parser.json_ld]

    report_index = json.loads(REPORT_INDEX.read_text(encoding="utf-8"))
    reports = report_index.get("reports", [])
    assert len(reports) == 15, f"Expected 15 current reports, found {len(reports)}"
    ids = [report.get("id") for report in reports]
    urls = [report.get("canonical_url") for report in reports]
    assert len(ids) == len(set(ids)), "Duplicate report IDs found"
    assert len(urls) == len(set(urls)), "Duplicate canonical report URLs found"
    missing_current_links = sorted(set(urls) - set(parser.links))
    assert not missing_current_links, (
        "Current reports missing from the public library: "
        + ", ".join(missing_current_links)
    )
    repeated_current_links = sorted(url for url in urls if parser.links.count(url) != 1)
    assert not repeated_current_links, (
        "Current reports must appear exactly once in the public library: "
        + ", ".join(repeated_current_links)
    )
    for report in reports:
        for field in ("id", "title", "edition", "publication_month", "scope", "canonical_url", "repository_record"):
            assert report.get(field), f"Missing {field} in report index entry"
        assert report["canonical_url"].startswith("https://openfutureforum.com/research/"), (
            f"Unexpected canonical report URL: {report['canonical_url']}"
        )
        assert (ROOT / report["repository_record"]).exists(), (
            f"Missing repository record: {report['repository_record']}"
        )

    item_lists: list[dict] = []
    for document in json_ld_documents:
        nodes = document.get("@graph", [document]) if isinstance(document, dict) else []
        for node in nodes:
            if not isinstance(node, dict) or node.get("@type") != "CollectionPage":
                continue
            main_entity = node.get("mainEntity")
            if isinstance(main_entity, dict) and main_entity.get("@type") == "ItemList":
                item_lists.append(main_entity)

    assert len(item_lists) == 1, "Expected one current-report ItemList in CollectionPage JSON-LD"
    item_list = item_lists[0]
    expected_items = [
        {
            "@type": "ListItem",
            "position": position,
            "name": report["title"],
            "url": report["canonical_url"],
        }
        for position, report in enumerate(reports, start=1)
    ]
    assert item_list.get("numberOfItems") == len(reports), "Structured report count does not match index"
    assert item_list.get("itemListElement") == expected_items, "Structured report list does not match index"

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
