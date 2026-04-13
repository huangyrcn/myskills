#!/usr/bin/env python3
"""
Extract URLs from PDF metadata and annotations.

Scans PDF for:
- Document metadata (URLs in info dict)
- Embedded links / annotations
- PDF metadata fields like 'Subject' or 'Keywords' that may contain URLs

Usage:
    python3 extract_urls_from_pdf.py paper.pdf
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls_from_metadata(doc: fitz.Document) -> list[dict]:
    """Extract URLs from PDF metadata."""
    results = []
    metadata = doc.metadata or {}

    for key, value in metadata.items():
        if not value:
            continue
        urls = URL_PATTERN.findall(str(value))
        for url in urls:
            results.append({
                "url": url,
                "source": f"metadata.{key}",
                "context": str(value)[:200],
            })

    return results


def extract_urls_from_annotations(doc: fitz.Document) -> list[dict]:
    """Extract URLs from PDF annotations (links)."""
    results = []

    for page_num, page in enumerate(doc):
        for link in page.get_links():
            uri = link.get("uri")
            if uri and URL_PATTERN.match(uri):
                # Get surrounding text context
                rect = link.get("rect")
                context = ""
                if rect:
                    # Expand rect slightly to get surrounding text
                    expanded = fitz.Rect(
                        rect.x0 - 50, rect.y0 - 20,
                        rect.x1 + 50, rect.y1 + 20
                    )
                    context = page.get_text("text", clip=expanded).strip()

                results.append({
                    "url": uri,
                    "source": f"annotation.page{page_num + 1}",
                    "context": context[:300],
                })

    return results


def extract_urls_from_text(doc: fitz.Document) -> list[dict]:
    """Scan full PDF text for URLs (especially github.com)."""
    results = []
    seen_urls = set()

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        urls = URL_PATTERN.findall(text)

        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Get context around the URL
            idx = text.find(url)
            start = max(0, idx - 100)
            end = min(len(text), idx + len(url) + 100)
            context = text[start:end].strip()

            # Filter to code-related URLs
            if "github.com" in url or "gitlab.com" in url or "bitbucket.org" in url:
                results.append({
                    "url": url,
                    "source": f"text.page{page_num + 1}",
                    "context": context,
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="Extract URLs from PDF")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    doc = fitz.open(pdf_path)

    all_results = []
    all_results.extend(extract_urls_from_metadata(doc))
    all_results.extend(extract_urls_from_annotations(doc))
    all_results.extend(extract_urls_from_text(doc))

    # Deduplicate by URL
    seen = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique_results.append(r)

    if args.json:
        print(json.dumps(unique_results, indent=2))
    else:
        if not unique_results:
            print("No URLs found in PDF")
        else:
            print(f"Found {len(unique_results)} URLs:")
            for r in unique_results:
                print(f"\n  URL: {r['url']}")
                print(f"  Source: {r['source']}")
                print(f"  Context: {r['context'][:100]}...")

    doc.close()


if __name__ == "__main__":
    main()