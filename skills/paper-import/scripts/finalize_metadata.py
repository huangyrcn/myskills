#!/usr/bin/env python3
"""
Finalize paper metadata after the model confirms venue, author, and method name.

Does NOT rename the actual storage directory under ~/papers/{title_slug}/.
Instead:
  1. Computes the short symlink name: {venue}{year}-{author}-{method}
  2. Creates a symlink in cwd -> ~/papers/{title_slug}/
  3. Writes confirmed_venue, author, method_name, foldername, symlink_path to metadata.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

from metadata_utils import compute_foldername, create_symlink_in_cwd, load_metadata, write_metadata


def finalize_metadata(
    metadata_path: Path, venue: str, method_name: str, author: str = ""
) -> tuple[Path, Path | None]:
    metadata = load_metadata(metadata_path)
    foldername = compute_foldername(metadata, venue, method_name, author=author)

    metadata["confirmed_venue"] = venue
    metadata["method_name"] = method_name
    metadata["foldername"] = foldername
    if author:
        metadata["author"] = author

    real_dir = metadata_path.parent.resolve()

    symlink_path = create_symlink_in_cwd(real_dir, foldername)

    metadata["symlink_path"] = str(symlink_path) if symlink_path else None

    write_metadata(metadata_path, metadata)
    return metadata_path, symlink_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize paper metadata and create symlink")
    parser.add_argument("--metadata", "-m", required=True, help="Path to metadata.yaml")
    parser.add_argument("--venue", required=True, help="Standardized venue token, e.g. neurips2017")
    parser.add_argument("--author", default="", help="Author short name (e.g. vaswani). Defaults to first author lastname.")
    parser.add_argument("--method", required=True, help="Method name extracted by the model")
    args = parser.parse_args()

    metadata_path, symlink_path = finalize_metadata(
        Path(args.metadata).resolve(), args.venue, args.method, author=args.author
    )
    print(f"metadata: {metadata_path}")
    if symlink_path:
        print(f"symlink:  {symlink_path}")


if __name__ == "__main__":
    main()
