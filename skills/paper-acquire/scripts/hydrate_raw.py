#!/usr/bin/env python3
"""
Hydrate or update the canonical raw bundle for a resolved paper metadata file.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[2]
LEGACY_SCRIPTS = SKILLS_ROOT / "paper-import" / "scripts"
if str(LEGACY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LEGACY_SCRIPTS))

import import_paper as legacy_import  # type: ignore
from metadata_utils import load_metadata, write_metadata  # type: ignore


def ensure_assets(metadata_path: Path) -> tuple[dict, Path, dict]:
    metadata = load_metadata(metadata_path)
    paper_dir = metadata_path.parent / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    assets = metadata.setdefault("assets", {})
    return metadata, paper_dir, assets


def persist_metadata(metadata_path: Path, metadata: dict) -> None:
    write_metadata(metadata_path, metadata)


def has_meaningful_source(path: Path) -> bool:
    return path.is_file() and len(path.read_text(encoding="utf-8", errors="ignore").strip()) > 500


def find_main_tex(paper_dir: Path) -> Path | None:
    explicit = paper_dir / "main.tex"
    if explicit.is_file():
        return explicit

    tex_files = sorted(paper_dir.glob("*.tex"))
    if not tex_files:
        return None
    return max(tex_files, key=lambda item: item.stat().st_size)


def convert_latex_to_source(metadata_path: Path) -> Path:
    metadata, paper_dir, assets = ensure_assets(metadata_path)
    source_path = paper_dir / "paper.md"
    main_tex = find_main_tex(paper_dir)
    if main_tex is None:
        raise FileNotFoundError("No usable TeX source found")

    subprocess.run(
        [
            "pandoc",
            "-f",
            "latex+raw_tex",
            "-t",
            "markdown+tex_math_dollars",
            main_tex.name,
            "-o",
            source_path.name,
        ],
        cwd=paper_dir,
        check=True,
    )

    if not has_meaningful_source(source_path):
        raise RuntimeError("Pandoc output is too small to trust")

    metadata["normalization"] = {
        "backend": "latex-pandoc",
        "source": "paper/paper.md",
    }
    assets["source"] = "paper/paper.md"
    persist_metadata(metadata_path, metadata)
    return source_path


def convert_pdf_to_source(metadata_path: Path, md_lang: str) -> Path:
    metadata, paper_dir, assets = ensure_assets(metadata_path)
    pdf_path = paper_dir / "paper.pdf"
    source_path = paper_dir / "paper.md"
    paper_md_path = paper_dir / "paper.md"

    if not pdf_path.is_file():
        raise FileNotFoundError(f"Missing PDF: {pdf_path}")

    script_path = legacy_import.resolve_pdf_to_md_script()
    subprocess.run(
        ["python3", str(script_path), str(pdf_path), "-l", md_lang],
        check=True,
    )

    if not paper_md_path.is_file():
        raise FileNotFoundError(f"Expected MinerU output missing: {paper_md_path}")

    shutil.copy2(paper_md_path, source_path)
    metadata["normalization"] = {
        "backend": "pdf-mineru",
        "source": "paper/paper.md",
    }
    assets["markdown"] = "paper/paper.md"
    assets["source"] = "paper/paper.md"
    persist_metadata(metadata_path, metadata)
    return source_path


def normalize_source(metadata_path: Path, md_lang: str) -> Path:
    metadata, paper_dir, assets = ensure_assets(metadata_path)
    source_path = paper_dir / "paper.md"
    if source_path.is_file() and assets.get("source"):
        return source_path

    try:
        return convert_latex_to_source(metadata_path)
    except Exception as exc:
        print(f"! LaTeX normalization failed, falling back to PDF: {exc}")
        return convert_pdf_to_source(metadata_path, md_lang)


def run_pipeline(
    metadata_path: Path,
    *,
    md_lang: str,
    clone_repo: bool,
    skip_pdf: bool,
    skip_latex: bool,
    skip_normalize: bool,
    skip_repo: bool,
) -> None:
    if not skip_pdf:
        pdf_path = legacy_import.download_pdf_asset(metadata_path)
        print(f"✓ PDF: {pdf_path}")

    if not skip_latex:
        try:
            latex_files = legacy_import.download_latex_asset(metadata_path)
        except Exception as exc:
            latex_files = []
            print(f"! LaTeX download failed: {exc}")
        if latex_files:
            print(f"✓ LaTeX: {', '.join(latex_files[:5])}")

    if not skip_normalize:
        source_path = normalize_source(metadata_path, md_lang)
        print(f"✓ Source: {source_path}")

    if not skip_repo:
        repo_search = legacy_import.find_repo(metadata_path, metadata_path.parent / "paper", clone_repo)
        selected = repo_search.get("selected")
        if selected:
            clone_state = "cloned" if selected.get("cloned_to") else "recorded only"
            print(f"✓ Repo: {selected['url']} ({selected.get('confidence', 'unknown')}, {clone_state})")
        else:
            print("! Repo: no candidate found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hydrate the canonical raw bundle for a resolved paper")
    parser.add_argument("--metadata", "-m", required=True, help="Path to metadata.yaml")
    parser.add_argument("--md-lang", default="en", choices=["en", "ch"], help="Language hint for PDF normalization")
    parser.add_argument("--no-clone-repo", action="store_true", help="Do not clone the selected repository")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF download")
    parser.add_argument("--skip-latex", action="store_true", help="Skip LaTeX download")
    parser.add_argument("--skip-normalize", action="store_true", help="Skip paper.md generation")
    parser.add_argument("--skip-repo", action="store_true", help="Skip repository discovery")
    args = parser.parse_args()

    run_pipeline(
        Path(args.metadata).resolve(),
        md_lang=args.md_lang,
        clone_repo=not args.no_clone_repo,
        skip_pdf=args.skip_pdf,
        skip_latex=args.skip_latex,
        skip_normalize=args.skip_normalize,
        skip_repo=args.skip_repo,
    )


if __name__ == "__main__":
    main()
