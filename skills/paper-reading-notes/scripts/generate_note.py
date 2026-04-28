#!/usr/bin/env python3
"""
Generate research-style reading notes from an existing raw bundle.

This script prepares the input context and determines the output path.
The actual note synthesis is typically done by the LLM agent using this skill.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add legacy scripts to path for metadata utilities
LEGACY_SCRIPTS = Path(__file__).resolve().parents[2] / "paper-import" / "scripts"
if str(LEGACY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LEGACY_SCRIPTS))

from metadata_utils import load_metadata  # type: ignore


def find_raw_bundle(query: str, papers_dir: Path) -> Path | None:
    """
    Find the raw bundle for a paper.

    query can be:
    - A path to the raw bundle directory
    - A path to metadata.yaml
    - A title slug
    - A paper title (will search ~/docs/papers)
    """
    query = query.strip()
    path = Path(query)

    # Direct path to bundle
    if path.exists():
        if path.is_dir():
            if (path / "metadata.yaml").exists():
                return path
        if path.name == "metadata.yaml":
            return path.parent
        return None

    # Check if it's a folder_slug in papers_dir
    slug_path = papers_dir / query
    if slug_path.is_dir() and (slug_path / "metadata.yaml").exists():
        return slug_path

    # Try to find by title
    if papers_dir.exists():
        from metadata_utils import normalize_title
        normalized = normalize_title(query)
        for child in papers_dir.iterdir():
            if child.is_symlink():
                continue
            metadata_path = child / "metadata.yaml"
            if metadata_path.exists():
                try:
                    metadata = load_metadata(metadata_path)
                    existing_title = normalize_title(metadata.get("title", ""))
                    if existing_title and existing_title == normalized:
                        return child
                except Exception:
                    continue

    return None


def get_repo_confidence(metadata: dict) -> tuple[str | None, str]:
    """
    Get repo information and confidence.

    Returns (repo_url, confidence_level).
    """
    repo_search = metadata.get("repo_search", {})
    selected = repo_search.get("selected")

    if selected:
        url = selected.get("url")
        confidence = selected.get("confidence", "unknown")
        return url, confidence

    return None, "none"


def determine_output_path(
    bundle_path: Path,
    *,
    user_output: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    """
    Determine the output path for the reading note.

    Rules:
    1. If user specifies output, use it.
    2. If cwd is not ~, write to ./papers/{folder_slug}/reading-note.md
    3. If cwd is ~, write to ~/tmp/paper-notes/{folder_slug}/reading-note.md
    """
    if user_output:
        return user_output

    if cwd is None:
        cwd = Path.cwd()

    metadata = load_metadata(bundle_path / "metadata.yaml")
    slug = metadata.get("folder_slug", bundle_path.name)

    home = Path.home()
    if cwd.resolve() == home.resolve():
        output_dir = home / "tmp" / "paper-notes" / slug
    else:
        output_dir = cwd / "papers" / slug

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "reading-note.md"


def prepare_note_context(bundle_path: Path) -> dict:
    """
    Prepare the context needed for note generation.
    """
    metadata_path = bundle_path / "metadata.yaml"
    metadata = load_metadata(metadata_path)

    paper_dir = bundle_path / "paper"
    source_path = paper_dir / "paper.md"
    main_tex_path = paper_dir / "main.tex"
    refs_path = paper_dir / "refs.bib"

    repo_dir = bundle_path / "repo"
    repo_search_path = bundle_path / "repo_search.json"

    # Get canonical info
    title = metadata.get("title", "")
    slug = metadata.get("folder_slug", bundle_path.name)

    # New schema
    identity = metadata.get("identity", {})
    bibliography = metadata.get("bibliography", {})
    urls = metadata.get("urls", {})

    canonical_url = identity.get("canonical_url") or urls.get("canonical") or ""
    authors = bibliography.get("authors") or metadata.get("authors", [])
    year = bibliography.get("year") or metadata.get("year")
    abstract = bibliography.get("abstract") or metadata.get("abstract")

    # Repo info
    repo_url, repo_confidence = get_repo_confidence(metadata)

    context = {
        "bundle_path": str(bundle_path),
        "title": title,
        "folder_slug": slug,
        "canonical_url": canonical_url,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "source_exists": source_path.exists(),
        "source_path": str(source_path) if source_path.exists() else None,
        "latex_exists": main_tex_path.exists(),
        "latex_path": str(main_tex_path) if main_tex_path.exists() else None,
        "refs_exists": refs_path.exists(),
        "repo_exists": repo_dir.exists(),
        "repo_url": repo_url,
        "repo_confidence": repo_confidence,
    }

    return context


def print_note_instructions(context: dict, output_path: Path) -> None:
    """
    Print instructions for the LLM to generate the note.
    """
    print("=" * 60)
    print("READING NOTE GENERATION CONTEXT")
    print("=" * 60)
    print()
    print(f"Title: {context['title']}")
    print(f"Slug: {context['folder_slug']}")
    print(f"Source URL: {context['canonical_url']}")
    print(f"Local Raw Path: {context['bundle_path']}")
    print()
    print("Authors:", ", ".join(context["authors"][:5]) if context["authors"] else "Unknown")
    print(f"Year: {context['year'] or 'Unknown'}")
    print()
    print("Available resources:")
    print(f"  - paper.md: {'Yes' if context['source_exists'] else 'No'}")
    print(f"  - LaTeX: {'Yes' if context['latex_exists'] else 'No'}")
    print(f"  - References: {'Yes' if context['refs_exists'] else 'No'}")
    print(f"  - Repository: {context['repo_url'] or 'None'} (confidence: {context['repo_confidence']})")
    print()
    print(f"Output path: {output_path}")
    print()
    print("=" * 60)
    print("REQUIRED NOTE STRUCTURE")
    print("=" * 60)
    print()
    print("The note must begin with:")
    print(f"  Source URL: {context['canonical_url']}")
    print(f"  Local Raw Path: {context['bundle_path']}")
    print()
    print("Required sections per note-ontology.md:")
    print("  1. One-sentence summary")
    print("  2. What problem does this paper really solve?")
    print("  3. Core idea")
    print("  4. Method pipeline")
    print("  5. Real contributions")
    print("  6. Hardest parts to understand")
    print("  7. Code alignment (or explicit uncertainty if no trustworthy repo)")
    print("  8. Experimental evidence")
    print("  9. Limitations and reproduction risks")
    print("  10. Reading path")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare context for reading note generation")
    parser.add_argument("query", help="Path to raw bundle, title slug, or paper title")
    parser.add_argument("--papers-dir", "-p", default="~/docs/papers", help="Directory for paper storage")
    parser.add_argument("--output", "-o", help="Output path for the reading note")
    parser.add_argument("--cwd", help="Working directory for determining output path")
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir).expanduser()
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    user_output = Path(args.output) if args.output else None

    # Find bundle
    bundle_path = find_raw_bundle(args.query, papers_dir)
    if not bundle_path:
        print(f"Error: Could not find raw bundle for '{args.query}'")
        sys.exit(1)

    print(f"Found bundle: {bundle_path}")

    # Prepare context
    context = prepare_note_context(bundle_path)

    # Determine output path
    output_path = determine_output_path(bundle_path, user_output=user_output, cwd=cwd)

    # Print instructions
    print_note_instructions(context, output_path)

    print("Ready for note generation. Use the context above to write the reading note.")


if __name__ == "__main__":
    main()
