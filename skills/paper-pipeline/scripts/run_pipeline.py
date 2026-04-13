#!/usr/bin/env python3
"""
Run the end-to-end paper workflow: resolve → acquire → reading-notes.

This script orchestrates the three stages and handles re-entry gracefully.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]


def run_resolve(query: str, papers_dir: Path, force: bool = False) -> Path:
    """
    Run paper-resolve to get metadata.yaml path.
    """
    script = SKILLS_ROOT / "paper-resolve" / "scripts" / "resolve_paper.py"
    cmd = [
        sys.executable,
        str(script),
        query,
        "--papers-dir", str(papers_dir),
    ]
    if force:
        cmd.append("--force")

    print(f"[resolve] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        raise RuntimeError("Resolve stage failed")

    # Find the metadata.yaml
    # The resolve script prints the path, but we can also search for it
    # For now, assume the query was a title and we need to find the slug
    # A better approach would be to have resolve output the path directly

    # Try to find it by scanning papers_dir for recent metadata
    if papers_dir.exists():
        metadata_files = sorted(
            papers_dir.glob("*/metadata.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if metadata_files:
            return metadata_files[0]

    raise RuntimeError("Could not find metadata.yaml after resolve")


def run_acquire(metadata_path: Path, md_lang: str = "en", clone_repo: bool = True) -> None:
    """
    Run paper-acquire to hydrate raw bundle.
    """
    script = SKILLS_ROOT / "paper-acquire" / "scripts" / "hydrate_raw.py"
    cmd = [
        sys.executable,
        str(script),
        "--metadata", str(metadata_path),
        "--md-lang", md_lang,
    ]
    if not clone_repo:
        cmd.append("--no-clone-repo")

    print(f"[acquire] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        raise RuntimeError("Acquire stage failed")


def run_reading_notes(bundle_path: Path, output_path: Path | None = None) -> Path:
    """
    Run paper-reading-notes to generate reading note.

    Returns the output path.
    """
    script = SKILLS_ROOT / "paper-reading-notes" / "scripts" / "generate_note.py"
    cmd = [
        sys.executable,
        str(script),
        str(bundle_path),
    ]
    if output_path:
        cmd.extend(["--output", str(output_path)])

    print(f"[reading-notes] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        raise RuntimeError("Reading-notes stage failed")

    # The script prints instructions; actual note generation is done by LLM
    # Return the expected output path
    if output_path:
        return output_path

    # Default output path logic
    from metadata_utils import load_metadata  # type: ignore
    metadata = load_metadata(bundle_path / "metadata.yaml")
    slug = metadata.get("title_slug", bundle_path.name)

    cwd = Path.cwd()
    home = Path.home()
    if cwd.resolve() == home.resolve():
        return home / "tmp" / "paper-notes" / slug / "reading-note.md"
    else:
        return cwd / "papers" / slug / "reading-note.md"


def check_existing_bundle(papers_dir: Path, query: str) -> Path | None:
    """
    Check if a bundle already exists for the query.
    """
    if not papers_dir.exists():
        return None

    # Try as slug
    slug_path = papers_dir / query
    if slug_path.is_dir() and (slug_path / "metadata.yaml").exists():
        return slug_path

    # Try to find by title
    from metadata_utils import normalize_title
    normalized = normalize_title(query)

    for child in papers_dir.iterdir():
        if child.is_symlink():
            continue
        metadata_path = child / "metadata.yaml"
        if metadata_path.exists():
            try:
                import yaml
                with open(metadata_path) as f:
                    metadata = yaml.safe_load(f)
                existing_title = normalize_title(metadata.get("title", ""))
                if existing_title and existing_title == normalized:
                    return child
            except Exception:
                continue

    return None


def run_pipeline(
    query: str,
    papers_dir: Path,
    *,
    md_lang: str = "en",
    clone_repo: bool = True,
    force_resolve: bool = False,
    force_acquire: bool = False,
    force_notes: bool = False,
    output_path: Path | None = None,
    skip_resolve: bool = False,
    skip_acquire: bool = False,
    skip_notes: bool = False,
) -> Path:
    """
    Run the full pipeline.

    Returns the path to the reading note.
    """
    bundle_path = None
    metadata_path = None

    # Stage 1: Resolve
    if not skip_resolve:
        # Check for existing bundle first
        existing = check_existing_bundle(papers_dir, query)
        if existing and not force_resolve:
            print(f"[pipeline] Found existing bundle: {existing}")
            bundle_path = existing
            metadata_path = existing / "metadata.yaml"
        else:
            metadata_path = run_resolve(query, papers_dir, force=force_resolve)
            bundle_path = metadata_path.parent
    else:
        # Assume bundle exists
        existing = check_existing_bundle(papers_dir, query)
        if not existing:
            raise RuntimeError(f"No existing bundle found for '{query}'")
        bundle_path = existing
        metadata_path = existing / "metadata.yaml"

    # Stage 2: Acquire
    if not skip_acquire:
        # Check if raw already complete
        paper_dir = bundle_path / "paper"
        pdf_path = paper_dir / "paper.pdf"
        source_path = paper_dir / "paper.md"

        if pdf_path.exists() and source_path.exists() and not force_acquire:
            print(f"[pipeline] Raw bundle already complete, skipping acquire")
        else:
            run_acquire(metadata_path, md_lang=md_lang, clone_repo=clone_repo)

    # Stage 3: Reading Notes
    if not skip_notes:
        # Check if note already exists
        expected_note = output_path or (
            Path.cwd() / "papers" / bundle_path.name / "reading-note.md"
        )

        if expected_note.exists() and not force_notes:
            print(f"[pipeline] Reading note already exists: {expected_note}")
        else:
            run_reading_notes(bundle_path, output_path=output_path)
    else:
        expected_note = bundle_path  # Just return bundle path

    return expected_note


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the end-to-end paper workflow")
    parser.add_argument("query", help="Paper title, DOI, arXiv ID, URL, or local path")
    parser.add_argument("--papers-dir", "-p", default="~/papers", help="Directory for paper storage")
    parser.add_argument("--output", "-o", help="Output path for reading note")
    parser.add_argument("--md-lang", default="en", choices=["en", "ch"], help="Language for PDF normalization")
    parser.add_argument("--no-clone-repo", action="store_true", help="Do not clone repository")
    parser.add_argument("--force-resolve", action="store_true", help="Force re-resolve even if bundle exists")
    parser.add_argument("--force-acquire", action="store_true", help="Force re-acquire even if raw exists")
    parser.add_argument("--force-notes", action="store_true", help="Force regenerate reading note")
    parser.add_argument("--skip-resolve", action="store_true", help="Skip resolve (use existing bundle)")
    parser.add_argument("--skip-acquire", action="store_true", help="Skip acquisition")
    parser.add_argument("--skip-notes", action="store_true", help="Skip reading note generation")
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir).expanduser()
    output_path = Path(args.output) if args.output else None

    try:
        result = run_pipeline(
            args.query,
            papers_dir,
            md_lang=args.md_lang,
            clone_repo=not args.no_clone_repo,
            force_resolve=args.force_resolve,
            force_acquire=args.force_acquire,
            force_notes=args.force_notes,
            output_path=output_path,
            skip_resolve=args.skip_resolve,
            skip_acquire=args.skip_acquire,
            skip_notes=args.skip_notes,
        )
        print(f"\n[pipeline] Complete. Output: {result}")
    except Exception as e:
        print(f"\n[pipeline] Failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
