#!/usr/bin/env python3
"""
Resolve a paper reference into canonical identity metadata.

Supports:
- Paper title
- DOI
- arXiv id or URL
- OpenReview URL
- Publisher/project URL
- Local PDF path
- Existing raw bundle reference

Outputs a metadata.yaml with the resolve schema plus legacy compatibility fields.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Add legacy scripts to path for reuse
LEGACY_SCRIPTS = Path(__file__).resolve().parents[2] / "paper-import" / "scripts"
if str(LEGACY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LEGACY_SCRIPTS))

from metadata_utils import find_existing_import, load_metadata, slugify, title_slug, write_metadata

# Import legacy providers and helpers
try:
    from providers import (
        Paper, ProviderResult, SearchQuery, SearchType,
        SemanticScholarProvider, ArxivProvider, OpenAlexProvider,
        OpenReviewProvider, CrossrefProvider, DblpProvider,
    )
    from query_apis import (
        choose_best_arxiv_id, choose_best_doi, exact_lookup,
        merge_papers, select_best_paper, similarity,
        normalize_title, normalize_author_tokens, author_overlap_ratio,
        DEFAULT_TITLE_SOURCES, DEFAULT_CONTEXT_SOURCES,
        TRUSTED_ARXIV_SOURCES, TRUSTED_DOI_SOURCES,
    )
    LEGACY_AVAILABLE = True
except ImportError:
    LEGACY_AVAILABLE = False


# === Input Type Detection ===

DOI_PATTERN = re.compile(r"^10\.\d{4,}/[^\s]+$", re.IGNORECASE)
ARXIV_ID_PATTERN = re.compile(
    r"(?:^|arxiv\.org/(?:abs|pdf|e-print)/|10\.48550/arxiv\.)"
    r"(?P<id>(?:[a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?",
    re.IGNORECASE,
)
OPENREVIEW_PATTERN = re.compile(
    r"openreview\.net/(?:forum\?id=|pdf\?id=|reference\?id=)(?P<id>[a-zA-Z0-9~-]+)",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
PDF_PATTERN = re.compile(r"\.pdf$", re.IGNORECASE)


class InputType:
    TITLE = "title"
    DOI = "doi"
    ARXIV_ID = "arxiv_id"
    OPENREVIEW_URL = "openreview_url"
    URL = "url"
    LOCAL_PDF = "local_pdf"
    LOCAL_BUNDLE = "local_bundle"


def detect_input_type(query: str) -> tuple[str, str]:
    """
    Detect the type of input and return (type, normalized_value).
    """
    query = query.strip()

    # Check for local path first
    path = Path(query)
    if path.exists():
        if path.is_dir():
            # Check if it's a raw bundle
            if (path / "metadata.yaml").exists():
                return InputType.LOCAL_BUNDLE, str(path.resolve())
            if path.name == "metadata.yaml":
                return InputType.LOCAL_BUNDLE, str(path.parent.resolve())
        if PDF_PATTERN.search(query):
            return InputType.LOCAL_PDF, str(path.resolve())

    # DOI
    doi_match = DOI_PATTERN.match(query)
    if doi_match:
        return InputType.DOI, query.lower()

    # DOI URL
    if "doi.org/" in query.lower():
        doi = query.lower().split("doi.org/")[-1].split("?")[0].split("#")[0]
        return InputType.DOI, doi

    # arXiv
    arxiv_match = ARXIV_ID_PATTERN.search(query)
    if arxiv_match:
        return InputType.ARXIV_ID, arxiv_match.group("id")

    # OpenReview
    openreview_match = OPENREVIEW_PATTERN.search(query)
    if openreview_match:
        return InputType.OPENREVIEW_URL, openreview_match.group("id")

    # Generic URL
    if URL_PATTERN.match(query):
        return InputType.URL, query

    # Default to title
    return InputType.TITLE, query


# === Local Bundle Scan ===

def scan_local_papers(papers_dir: Path, *, title: Optional[str] = None, doi: Optional[str] = None) -> Optional[Path]:
    """
    Scan ~/papers for an existing bundle matching title or DOI.
    """
    if not papers_dir.exists():
        return None

    normalized_title = normalize_title(title) if title else None

    for child in papers_dir.iterdir():
        if child.is_symlink():
            continue
        metadata_path = child / "metadata.yaml"
        if not metadata_path.is_file():
            continue

        try:
            metadata = load_metadata(metadata_path)
        except Exception:
            continue

        # Check DOI match
        if doi:
            existing_doi = None
            # Check new schema first
            identity = metadata.get("identity", {})
            aliases = identity.get("aliases", {})
            existing_doi = aliases.get("doi")
            # Fall back to legacy schema
            if not existing_doi:
                identifiers = metadata.get("identifiers", {})
                existing_doi = identifiers.get("doi")
            if existing_doi and existing_doi.lower() == doi.lower():
                return child

        # Check title match
        if normalized_title:
            existing_title = normalize_title(metadata.get("title", ""))
            if existing_title and existing_title == normalized_title:
                return child

    return None


# === Resolution Functions ===

def resolve_by_doi(doi: str, providers: list) -> Optional[dict]:
    """Resolve paper by DOI using providers."""
    if not LEGACY_AVAILABLE:
        return None

    results = []
    for provider_class in providers:
        try:
            query = SearchQuery(query=doi, search_type=SearchType.DOI)
            provider = provider_class()
            result = provider.search(query)
            if result and result.papers:
                results.extend(result.papers)
        except Exception:
            continue

    if not results:
        return None

    # Exact DOI match - return first
    best = results[0]
    # Build URL from available identifiers
    url = None
    if doi:
        url = f"https://doi.org/{doi}"
    elif best.arxiv_id:
        url = f"https://arxiv.org/abs/{best.arxiv_id}"
    elif best.openalex_id:
        url = f"https://openalex.org/{best.openalex_id}"

    return {
        "title": best.title,
        "authors": best.authors or [],
        "year": best.year,
        "venue": best.venue,
        "abstract": best.abstract,
        "doi": doi,
        "arxiv_id": best.arxiv_id,
        "s2_id": best.s2_id,
        "openalex_id": best.openalex_id,
        "url": url,
        "pdf_url": best.pdf_url,
    }


def resolve_by_arxiv(arxiv_id: str, providers: list) -> Optional[dict]:
    """Resolve paper by arXiv ID using providers."""
    if not LEGACY_AVAILABLE:
        return None

    # Try arXiv provider first
    try:
        provider = ArxivProvider()
        query = SearchQuery(query=arxiv_id, search_type=SearchType.ARXIV)
        result = provider.search(query)
        if result and result.papers:
            best = result.papers[0]
            return {
                "title": best.title,
                "authors": best.authors or [],
                "year": best.year,
                "venue": best.venue,
                "abstract": best.abstract,
                "doi": getattr(best, "doi", None),
                "arxiv_id": arxiv_id,
                "s2_id": getattr(best, "s2_id", None),
                "openalex_id": getattr(best, "openalex_id", None),
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            }
    except Exception:
        pass

    return None


def resolve_by_openreview(openreview_id: str) -> Optional[dict]:
    """Resolve paper by OpenReview ID."""
    if not LEGACY_AVAILABLE:
        return None

    try:
        provider = OpenReviewProvider()
        query = SearchQuery(query=openreview_id, search_type=SearchType.AUTO)
        result = provider.search(query)
        if result and result.papers:
            best = result.papers[0]
            return {
                "title": best.title,
                "authors": best.authors or [],
                "year": best.year,
                "venue": best.venue,
                "abstract": best.abstract,
                "doi": getattr(best, "doi", None),
                "arxiv_id": getattr(best, "arxiv_id", None),
                "s2_id": getattr(best, "s2_id", None),
                "openalex_id": getattr(best, "openalex_id", None),
                "openreview_id": openreview_id,
                "url": f"https://openreview.net/forum?id={openreview_id}",
                "pdf_url": getattr(best, "pdf_url", None),
            }
    except Exception:
        pass

    return None


def resolve_by_title(title: str, papers_dir: Path) -> Optional[dict]:
    """Resolve paper by title using provider fusion."""
    if not LEGACY_AVAILABLE:
        print("Warning: Legacy providers not available, cannot resolve by title")
        return None

    # Check local first
    local = scan_local_papers(papers_dir, title=title)
    if local:
        metadata = load_metadata(local / "metadata.yaml")
        return {
            "title": metadata.get("title"),
            "authors": metadata.get("bibliography", {}).get("authors") or metadata.get("authors", []),
            "year": metadata.get("bibliography", {}).get("year") or metadata.get("year"),
            "venue": metadata.get("bibliography", {}).get("venue") or metadata.get("venue"),
            "abstract": metadata.get("bibliography", {}).get("abstract") or metadata.get("abstract"),
            "doi": metadata.get("identity", {}).get("aliases", {}).get("doi") or metadata.get("identifiers", {}).get("doi"),
            "arxiv_id": metadata.get("identity", {}).get("aliases", {}).get("arxiv") or metadata.get("identifiers", {}).get("arxiv"),
            "s2_id": metadata.get("identity", {}).get("aliases", {}).get("semantic_scholar") or metadata.get("identifiers", {}).get("semantic_scholar"),
            "openalex_id": metadata.get("identity", {}).get("aliases", {}).get("openalex") or metadata.get("identifiers", {}).get("openalex"),
            "openreview_id": metadata.get("identity", {}).get("aliases", {}).get("openreview") or metadata.get("identifiers", {}).get("openreview"),
            "url": metadata.get("identity", {}).get("canonical_url") or metadata.get("urls", {}).get("canonical"),
            "pdf_url": metadata.get("urls", {}).get("pdf") or (metadata.get("pdf_urls") or [None])[0],
            "local_path": str(local),
        }

    # Use provider fusion
    providers = [
        SemanticScholarProvider,
        ArxivProvider,
        OpenAlexProvider,
        CrossrefProvider,
        DblpProvider,
    ]

    all_papers = []
    for provider_class in providers:
        try:
            provider = provider_class()
            query = SearchQuery(query=title, search_type=SearchType.TITLE)
            result = provider.search(query)
            if result and result.papers:
                all_papers.extend(result.papers)
        except Exception:
            continue

    if not all_papers:
        return None

    # Select best match
    best = select_best_paper(all_papers, title)
    if not best:
        return None

    # Merge identifiers from other papers
    arxiv_id, _ = choose_best_arxiv_id(all_papers, best)
    doi, _ = choose_best_doi(all_papers, best, arxiv_id)

    # Build URL from available identifiers
    url = None
    if doi:
        url = f"https://doi.org/{doi}"
    elif arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    elif best.openalex_id:
        url = f"https://openalex.org/{best.openalex_id}"

    return {
        "title": best.title,
        "authors": best.authors or [],
        "year": best.year,
        "venue": best.venue,
        "abstract": best.abstract,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "s2_id": best.s2_id,
        "openalex_id": best.openalex_id,
        "openreview_id": best.openreview_id,
        "url": url,
        "pdf_url": best.pdf_url,
    }


# === Metadata Construction ===

def build_resolve_metadata(resolved: dict, *, title_slug_override: Optional[str] = None) -> dict:
    """
    Build the full metadata.yaml content with resolve schema + legacy compatibility.
    """
    now = datetime.now().isoformat()

    title = resolved.get("title", "")
    slug = title_slug_override or title_slug(title)

    # Determine primary ID type and value
    arxiv_id = resolved.get("arxiv_id")
    doi = resolved.get("doi")
    openreview_id = resolved.get("openreview_id")
    s2_id = resolved.get("s2_id")
    openalex_id = resolved.get("openalex_id")

    # Primary ID selection: arXiv > DOI > OpenReview > OpenAlex
    if arxiv_id:
        primary_type = "arxiv"
        primary_value = arxiv_id
        canonical_url = f"https://arxiv.org/abs/{arxiv_id}"
    elif doi:
        primary_type = "doi"
        primary_value = doi
        canonical_url = f"https://doi.org/{doi}"
    elif openreview_id:
        primary_type = "openreview"
        primary_value = openreview_id
        canonical_url = f"https://openreview.net/forum?id={openreview_id}"
    elif openalex_id:
        primary_type = "openalex"
        primary_value = openalex_id
        canonical_url = resolved.get("url", "")
    else:
        primary_type = "url"
        primary_value = canonical_url = resolved.get("url", "")

    # Build new schema
    metadata = {
        "created_at": now,
        "title": title,
        "title_slug": slug,

        "identity": {
            "canonical_url": canonical_url,
            "primary_id": {
                "type": primary_type,
                "value": primary_value,
            },
            "aliases": {
                "doi": doi,
                "arxiv": arxiv_id,
                "openreview": openreview_id,
                "openalex": openalex_id,
                "semantic_scholar": s2_id,
            },
            "resolution_confidence": "high" if (arxiv_id or doi or openreview_id) else "medium",
            "resolution_evidence": [
                f"Resolved via {primary_type}" + (f": {primary_value}" if primary_value else ""),
            ],
        },

        "bibliography": {
            "authors": resolved.get("authors", []),
            "year": resolved.get("year"),
            "venue": resolved.get("venue"),
            "venue_context": None,
            "publication_status": "unknown",
            "abstract": resolved.get("abstract"),
        },

        "urls": {
            "canonical": canonical_url,
            "pdf": resolved.get("pdf_url"),
            "doi": f"https://doi.org/{doi}" if doi else None,
            "openreview": f"https://openreview.net/forum?id={openreview_id}" if openreview_id else None,
        },
    }

    # Add legacy compatibility fields
    metadata.update({
        "authors": resolved.get("authors", []),
        "year": resolved.get("year"),
        "venue": resolved.get("venue"),
        "abstract": resolved.get("abstract"),

        "identifiers": {
            "doi": doi,
            "arxiv": arxiv_id,
            "semantic_scholar": s2_id,
            "openalex": openalex_id,
            "openreview": openreview_id,
        },

        "pdf_urls": [resolved["pdf_url"]] if resolved.get("pdf_url") else [],

        "latex_source": {
            "available": bool(arxiv_id),
            "url": f"https://arxiv.org/e-print/{arxiv_id}" if arxiv_id else None,
        } if arxiv_id else {
            "available": False,
            "note": "only_arxiv_has_latex_source",
        },

        "assets": {},
        "repo_search": {
            "selected": None,
            "candidates": [],
        },
    })

    # Note if resolved from local
    if resolved.get("local_path"):
        metadata["identity"]["resolution_evidence"].append(
            f"Found existing local bundle at {resolved['local_path']}"
        )

    return metadata


# === Main ===

def resolve_paper(
    query: str,
    papers_dir: Path,
    output_dir: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """
    Resolve a paper reference and write metadata.yaml.

    Returns the path to the metadata.yaml file.
    """
    # Detect input type
    input_type, normalized = detect_input_type(query)
    print(f"Input type: {input_type}")
    print(f"Normalized: {normalized}")

    # Handle local bundle directly
    if input_type == InputType.LOCAL_BUNDLE:
        bundle_path = Path(normalized)
        metadata_path = bundle_path / "metadata.yaml"
        print(f"Using existing local bundle: {bundle_path}")
        return metadata_path

    # Prepare output directory
    if output_dir is None:
        output_dir = papers_dir

    # Resolve based on input type
    resolved = None

    if input_type == InputType.DOI:
        print(f"Resolving by DOI: {normalized}")
        providers = [CrossrefProvider, SemanticScholarProvider, OpenAlexProvider]
        resolved = resolve_by_doi(normalized, providers)

    elif input_type == InputType.ARXIV_ID:
        print(f"Resolving by arXiv ID: {normalized}")
        resolved = resolve_by_arxiv(normalized, [])

    elif input_type == InputType.OPENREVIEW_URL:
        print(f"Resolving by OpenReview ID: {normalized}")
        resolved = resolve_by_openreview(normalized)

    elif input_type == InputType.TITLE:
        print(f"Resolving by title: {normalized}")
        resolved = resolve_by_title(normalized, papers_dir)

    elif input_type == InputType.URL:
        # For generic URLs, try to extract identifiers
        print(f"Resolving URL: {normalized}")
        arxiv_match = ARXIV_ID_PATTERN.search(normalized)
        if arxiv_match:
            resolved = resolve_by_arxiv(arxiv_match.group("id"), [])
        elif "doi.org/" in normalized.lower():
            doi = normalized.lower().split("doi.org/")[-1].split("?")[0].split("#")[0]
            providers = [CrossrefProvider, SemanticScholarProvider]
            resolved = resolve_by_doi(doi, providers)
        else:
            # Fall back to title search if we can extract a title
            print("Warning: Cannot extract identifiers from URL, falling back to title search")
            resolved = resolve_by_title(normalized, papers_dir)

    elif input_type == InputType.LOCAL_PDF:
        print(f"Local PDF path provided: {normalized}")
        print("Warning: Local PDF resolution not yet implemented, would need to extract metadata from PDF")
        # For now, create a minimal metadata entry
        resolved = {
            "title": Path(normalized).stem.replace("_", " "),
            "authors": [],
            "year": None,
            "venue": None,
            "abstract": None,
            "doi": None,
            "arxiv_id": None,
            "url": None,
            "pdf_url": normalized,
        }

    if not resolved:
        raise RuntimeError(f"Could not resolve paper: {query}")

    print(f"Resolved: {resolved.get('title')}")

    # Build metadata
    metadata = build_resolve_metadata(resolved)

    # Determine output path
    slug = metadata["title_slug"]
    paper_dir = output_dir / slug

    # Check for existing
    if paper_dir.exists() and not force:
        existing_metadata_path = paper_dir / "metadata.yaml"
        if existing_metadata_path.exists():
            print(f"Metadata already exists: {existing_metadata_path}")
            print("Use --force to overwrite")
            return existing_metadata_path

    # Write metadata
    paper_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = paper_dir / "metadata.yaml"
    write_metadata(metadata_path, metadata)

    print(f"Wrote metadata: {metadata_path}")
    print(f"Title: {metadata['title']}")
    print(f"Canonical URL: {metadata['identity']['canonical_url']}")
    print(f"Resolution confidence: {metadata['identity']['resolution_confidence']}")

    return metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a paper reference into canonical identity metadata")
    parser.add_argument("query", help="Paper title, DOI, arXiv ID/URL, OpenReview URL, or local path")
    parser.add_argument("--papers-dir", "-p", default="~/papers", help="Directory for paper storage (default: ~/papers)")
    parser.add_argument("--output", "-o", help="Output directory for metadata (default: papers-dir)")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing metadata")
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir).expanduser()
    output_dir = Path(args.output).expanduser() if args.output else papers_dir

    resolve_paper(args.query, papers_dir, output_dir, args.force)


if __name__ == "__main__":
    main()
