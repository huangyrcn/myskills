#!/usr/bin/env python3
"""
Finalize paper metadata after the model confirms venue and method name.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from metadata_utils import compute_foldername, load_metadata, write_metadata


def finalize_metadata(metadata_path: Path, venue: str, method_name: str) -> Path:
    metadata = load_metadata(metadata_path)
    foldername = compute_foldername(metadata, venue, method_name)

    metadata["confirmed_venue"] = venue
    metadata["method_name"] = method_name
    metadata["foldername"] = foldername

    current_dir = metadata_path.parent
    target_dir = current_dir.parent / foldername
    if target_dir.exists() and target_dir != current_dir:
        raise FileExistsError(f"Target directory already exists: {target_dir}")

    if current_dir != target_dir:
        current_dir.rename(target_dir)
        metadata_path = target_dir / "metadata.yaml"

    write_metadata(metadata_path, metadata)
    return metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize paper metadata and rename directory")
    parser.add_argument("--metadata", "-m", required=True, help="Path to metadata.yaml")
    parser.add_argument("--venue", required=True, help="Standardized venue token, e.g. neurips")
    parser.add_argument("--method", required=True, help="Method name extracted by the model")
    args = parser.parse_args()

    metadata_path = finalize_metadata(Path(args.metadata).resolve(), args.venue, args.method)
    print(metadata_path)


if __name__ == "__main__":
    main()
