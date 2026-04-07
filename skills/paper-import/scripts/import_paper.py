#!/usr/bin/env python3
"""
Run the full paper-import asset pipeline after metadata is finalized.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from download_pdf import download_from_metadata
from find_repo import find_repo
from metadata_utils import load_metadata, write_metadata


def resolve_pdf_to_md_script() -> Path:
    skills_root = Path(__file__).resolve().parents[2]
    script_path = skills_root / "pdf-to-md" / "scripts" / "mineru-api.py"
    if not script_path.is_file():
        raise FileNotFoundError(f"pdf-to-md script not found: {script_path}")
    return script_path


def ensure_assets(metadata_path: Path) -> tuple[dict, Path, dict]:
    metadata = load_metadata(metadata_path)
    paper_dir = metadata_path.parent / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    assets = metadata.setdefault("assets", {})
    return metadata, paper_dir, assets


def persist_metadata(metadata_path: Path, metadata: dict) -> None:
    write_metadata(metadata_path, metadata)


def download_pdf_asset(metadata_path: Path) -> Path:
    metadata, paper_dir, assets = ensure_assets(metadata_path)

    # If PDF already exists and is substantial, skip download
    pdf_path = paper_dir / "paper.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 10000:
        if not assets.get("pdf"):
            assets["pdf"] = "paper/paper.pdf"
            persist_metadata(metadata_path, metadata)
        return pdf_path

    success = download_from_metadata(str(metadata_path), str(paper_dir))
    if not success:
        raise RuntimeError("PDF download failed")
    assets["pdf"] = "paper/paper.pdf"
    persist_metadata(metadata_path, metadata)
    return paper_dir / "paper.pdf"


def download_latex_asset(metadata_path: Path) -> list[str]:
    metadata, paper_dir, assets = ensure_assets(metadata_path)

    # If LaTeX files physically exist on disk, scan and register them
    existing_tex = [f for f in paper_dir.iterdir() if f.suffix == '.tex']
    if existing_tex and not assets.get("latex_dir"):
        if not assets.get("latex_files"):
            assets["latex_dir"] = "paper/"
            assets["latex_files"] = sorted(f.name for f in existing_tex)
            persist_metadata(metadata_path, metadata)
        return sorted(f.name for f in existing_tex)

    # If LaTeX assets already recorded, skip download
    if assets.get("latex_dir") or assets.get("latex_files"):
        return sorted(assets.get("latex_files", []))

    latex_source = metadata.get("latex_source", {}) or {}
    if not latex_source.get("available") or not latex_source.get("url"):
        return []

    url = latex_source["url"]
    moved_files: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="paper-import-latex-") as temp_dir:
        archive_path = Path(temp_dir) / "latex_src"
        with urllib.request.urlopen(url, timeout=60) as response:
            archive_path.write_bytes(response.read())

        # arXiv e-print returns a PDF, not a LaTeX tarball — skip if so
        with open(archive_path, "rb") as f:
            header = f.read(5)
        if header.startswith(b"%PDF"):
            print("! LaTeX: arXiv e-print returned a PDF, not a LaTeX source archive — skipping")
            return []

        extract_dir = Path(temp_dir) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive_path, "r:*") as archive:
                archive.extractall(extract_dir)
        except (tarfile.TarError, EOFError, OSError) as exc:
            print(f"! LaTeX: cannot extract archive ({exc}) — skipping")
            return []

        for suffix in ("*.tex", "*.bib"):
            for source_file in extract_dir.rglob(suffix):
                target = paper_dir / source_file.name
                if target.exists():
                    target = paper_dir / f"{source_file.stem}_{len(moved_files)}{source_file.suffix}"
                shutil.move(str(source_file), target)
                moved_files.append(target)

    tex_files = [path for path in moved_files if path.suffix == ".tex"]
    bib_files = [path for path in moved_files if path.suffix == ".bib"]
    if tex_files and not (paper_dir / "main.tex").exists():
        preferred = max(tex_files, key=lambda item: item.stat().st_size)
        if preferred.name != "main.tex":
            shutil.copy2(preferred, paper_dir / "main.tex")
    if bib_files and not (paper_dir / "refs.bib").exists():
        preferred = bib_files[0]
        if preferred.name != "refs.bib":
            shutil.copy2(preferred, paper_dir / "refs.bib")

    if moved_files:
        assets["latex_dir"] = "paper/"
        assets["latex_files"] = sorted(path.name for path in moved_files)
        persist_metadata(metadata_path, metadata)
    return sorted(path.name for path in moved_files)


def convert_pdf_to_markdown(metadata_path: Path, md_lang: str) -> Path:
    metadata, paper_dir, assets = ensure_assets(metadata_path)
    pdf_path = paper_dir / "paper.pdf"
    markdown_path = paper_dir / "paper.md"

    # If Markdown already exists and is recorded in assets, skip conversion
    if markdown_path.is_file() and assets.get("markdown"):
        return markdown_path

    if not pdf_path.is_file():
        raise FileNotFoundError(f"Missing PDF: {pdf_path}")

    script_path = resolve_pdf_to_md_script()
    subprocess.run(
        ["python3", str(script_path), str(pdf_path), "-l", md_lang],
        check=True,
    )

    markdown_path = paper_dir / "paper.md"
    if not markdown_path.is_file():
        raise FileNotFoundError(f"Markdown output missing: {markdown_path}")
    assets["markdown"] = "paper/paper.md"
    persist_metadata(metadata_path, metadata)
    return markdown_path


def run_pipeline(metadata_path: Path, *, md_lang: str, clone_repo: bool, skip_repo: bool) -> None:
    pdf_path = download_pdf_asset(metadata_path)
    print(f"✓ PDF: {pdf_path}")

    try:
        latex_files = download_latex_asset(metadata_path)
    except Exception as exc:
        latex_files = []
        print(f"! LaTeX: {exc}")
    if latex_files:
        print(f"✓ LaTeX: {', '.join(latex_files[:5])}")

    markdown_path = convert_pdf_to_markdown(metadata_path, md_lang)
    print(f"✓ Markdown: {markdown_path}")

    if not skip_repo:
        repo_search = find_repo(metadata_path, metadata_path.parent / "paper", clone_repo)
        selected = repo_search.get("selected")
        if selected:
            clone_state = "cloned" if selected.get("cloned_to") else "recorded only"
            print(f"✓ Repo: {selected['url']} ({selected.get('confidence', 'unknown')}, {clone_state})")
        else:
            print("! Repo: no candidate found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import paper assets from finalized metadata")
    parser.add_argument("--metadata", "-m", required=True, help="Path to finalized metadata.yaml")
    parser.add_argument("--md-lang", default="en", choices=["en", "ch"], help="Language hint for pdf-to-md")
    parser.add_argument("--no-clone-repo", action="store_true", help="Do not clone the selected repository")
    parser.add_argument("--skip-repo", action="store_true", help="Skip repo discovery entirely")
    args = parser.parse_args()

    run_pipeline(
        Path(args.metadata).resolve(),
        md_lang=args.md_lang,
        clone_repo=not args.no_clone_repo,
        skip_repo=args.skip_repo,
    )


if __name__ == "__main__":
    main()
