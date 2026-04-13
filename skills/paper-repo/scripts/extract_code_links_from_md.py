#!/usr/bin/env python3
"""
Extract code-related links from paper.md with surrounding context.

Scans markdown for:
- Explicit code links (github.com, gitlab.com, bitbucket.org)
- Phrases like "code available at", "implementation at", "repository at"
- URLs in context of code/project mentions

Returns URL + 2 lines above and 2 lines below for Agent to judge.

Usage:
    python3 extract_code_links_from_md.py paper.md
"""

import argparse
import json
import re
import sys
from pathlib import Path


URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

CODE_HOSTS = ["github.com", "gitlab.com", "bitbucket.org", "codeberg.org"]

CODE_KEYWORDS = [
    "code",
    "implementation",
    "repository",
    "repo",
    "source",
    "available at",
    "project",
    "github",
]


def extract_code_links(content: str) -> list[dict]:
    """Extract code-related links with context."""
    results = []
    lines = content.split("\n")

    # Process each line
    for i, line in enumerate(lines):
        urls = URL_PATTERN.findall(line)

        for url in urls:
            # Check if URL is a code host
            is_code_host = any(host in url for host in CODE_HOSTS)

            # Check if context mentions code keywords
            context_window = lines[max(0, i - 2): min(len(lines), i + 3)]
            context_text = "\n".join(context_window)
            has_code_keyword = any(kw.lower() in context_text.lower() for kw in CODE_KEYWORDS)

            if is_code_host or has_code_keyword:
                # Get 2 lines above + current + 2 lines below
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = lines[start:end]

                results.append({
                    "url": url,
                    "line_number": i + 1,
                    "context_above": lines[start:i] if start < i else [],
                    "context_line": line,
                    "context_below": lines[i + 1:end] if i + 1 < end else [],
                    "is_code_host": is_code_host,
                })

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    return unique


def format_output(results: list[dict], use_json: bool = False) -> str:
    """Format results for output."""
    if use_json:
        return json.dumps(results, indent=2)

    if not results:
        return "No code-related links found in paper.md"

    output = f"Found {len(results)} code-related links:\n"

    for r in results:
        output += f"\n{'=' * 60}\n"
        output += f"URL: {r['url']}\n"
        output += f"Line: {r['line_number']}\n"
        output += f"Code host: {r['is_code_host']}\n"
        output += f"\nContext (2 lines above / current / 2 lines below):\n"

        if r["context_above"]:
            for line in r["context_above"]:
                output += f"  ↑ {line[:80]}\n"

        output += f"  >>> {r['context_line'][:80]}\n"

        if r["context_below"]:
            for line in r["context_below"]:
                output += f"  ↓ {line[:80]}\n"

    return output


def main():
    parser = argparse.ArgumentParser(description="Extract code links from paper.md")
    parser.add_argument("md_path", help="Path to paper.md")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    md_path = Path(args.md_path)
    if not md_path.exists():
        print(f"Error: paper.md not found: {md_path}")
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8", errors="ignore")
    results = extract_code_links(content)
    print(format_output(results, use_json=args.json))


if __name__ == "__main__":
    main()