#!/usr/bin/env python3
"""
Shared helpers for paper-import metadata and naming.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import yaml


def slugify(text: str, *, sep: str = "-", max_length: Optional[int] = None) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    text = re.sub(rf"{re.escape(sep)}+", sep, text).strip(sep)
    if not text:
        text = "paper"
    if max_length is not None:
        text = text[:max_length].rstrip(sep) or "paper"
    return text


def normalize_title(title: str) -> str:
    return slugify(title, sep=" ", max_length=240)


def title_slug(title: str) -> str:
    return slugify(title, sep="_", max_length=80)


def standardize_venue_token(venue: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "", (venue or "").lower())
    return token or "arxiv"


def first_author_lastname(authors: list[str]) -> str:
    if not authors:
        return "unknown"
    lastname = authors[0].split()[-1]
    return slugify(lastname, sep="-", max_length=40)


def sanitize_method_name(method_name: str) -> str:
    return slugify(method_name, sep="-", max_length=15)


def compute_foldername(metadata: dict, venue: str, method_name: str) -> str:
    year = metadata.get("year") or "unknown"
    lastname = first_author_lastname(metadata.get("authors", []))
    venue_token = standardize_venue_token(venue)
    method_token = sanitize_method_name(method_name)
    return f"{venue_token}{year}-{lastname}-{method_token}"


def load_metadata(metadata_path: Path) -> dict:
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid metadata YAML: {metadata_path}")
    return data


def write_metadata(metadata_path: Path, metadata: dict) -> None:
    with metadata_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            metadata,
            handle,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )


def find_existing_import(output_dir: Path, *, title: str, doi: Optional[str]) -> Optional[Path]:
    if not output_dir.exists():
        return None
    normalized_title = normalize_title(title)
    for child in output_dir.iterdir():
        metadata_path = child / "metadata.yaml"
        if not metadata_path.is_file():
            continue
        try:
            metadata = load_metadata(metadata_path)
        except Exception:
            continue
        existing_title = normalize_title(metadata.get("title", ""))
        identifiers = metadata.get("identifiers", {}) or {}
        existing_doi = identifiers.get("doi")
        if existing_title and existing_title == normalized_title:
            return child
        if doi and existing_doi and existing_doi.lower() == doi.lower():
            return child
    return None
