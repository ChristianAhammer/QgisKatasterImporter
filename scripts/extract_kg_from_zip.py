#!/usr/bin/env python3
"""Safely extract a named KG folder from ZIP archives in a rawdata root."""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path


class UnsafeZipPathError(ValueError):
    """Raised when a ZIP entry would escape the output root."""


def _normalized_entry_parts(entry_name: str) -> list[str]:
    parts = []
    for part in entry_name.replace("\\", "/").split("/"):
        if not part or part == ".":
            continue
        if part == ".." or part.endswith(":"):
            raise UnsafeZipPathError(f"Unsafe ZIP entry path: {entry_name}")
        parts.append(part)
    return parts


def _resolve_output_path(output_root: Path, rel_parts: list[str]) -> Path:
    root = output_root.resolve()
    target = (output_root / Path(*rel_parts)).resolve()
    if target != root and root not in target.parents:
        raise UnsafeZipPathError(f"ZIP entry escapes output root: {'/'.join(rel_parts)}")
    return target


def extract_matching_folder(zip_path: Path, output_root: Path, wanted_folder: str) -> bool:
    found = False
    wanted_lower = wanted_folder.lower()

    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            parts = _normalized_entry_parts(entry.filename)
            if not parts:
                continue

            folder_index = next((i for i, part in enumerate(parts) if part.lower() == wanted_lower), -1)
            if folder_index < 0:
                continue

            rel_parts = parts[folder_index:]
            target = _resolve_output_path(output_root, rel_parts)
            found = True

            if entry.is_dir() or entry.filename.endswith(("/", "\\")):
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)

    return found


def extract_from_zip_root(zip_root: Path, output_root: Path, wanted_folder: str) -> bool:
    found = False
    for zip_path in sorted(zip_root.glob("*.zip")):
        if extract_matching_folder(zip_path, output_root, wanted_folder):
            found = True
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a named KG folder from ZIP archives.")
    parser.add_argument("--zip-root", required=True, help="Folder containing ZIP archives.")
    parser.add_argument("--output-root", required=True, help="Destination root for extracted files.")
    parser.add_argument("--folder", required=True, help="Folder name to extract, typically a 5-digit KG number.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    zip_root = Path(args.zip_root)
    output_root = Path(args.output_root)

    if not zip_root.is_dir():
        print(f"ZIP root not found: {zip_root}", file=sys.stderr)
        return 1

    output_root.mkdir(parents=True, exist_ok=True)

    try:
        found = extract_from_zip_root(zip_root, output_root, args.folder)
    except UnsafeZipPathError as err:
        print(f"Unsafe ZIP entry rejected: {err}", file=sys.stderr)
        return 1
    except zipfile.BadZipFile as err:
        print(f"Invalid ZIP archive: {err}", file=sys.stderr)
        return 1

    if not found:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
