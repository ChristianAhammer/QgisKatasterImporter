#!/usr/bin/env python3
"""Discover and parse Katastralgemeinde number/name mappings."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


CANDIDATE_FILENAMES = (
    "kg_mapping.csv",
    "katastralgemeindenverzeichnis.csv",
    "katastralgemeinde_verzeichnis.csv",
    "kg_verzeichnis.csv",
    "kg-verzeichnis.csv",
    "kgvz.csv",
)

CSV_KEYWORDS = ("kg", "katastral", "gemeinde", "verzeichnis", "mapping")
ZIP_KEYWORDS = ("kg", "katastral", "gemeinde", "verzeichnis")

NUMBER_HEADERS = {
    "kgnummer",
    "katastralgemeindenummer",
    "kgnr",
    "kgnr",
    "kgcode",
    "katastralgemeindecode",
}

NAME_HEADERS = {
    "kgname",
    "katastralgemeindename",
    "katastralgemeinde",
    "gemeindename",
    "name",
}


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode CSV file: {path}")


def pick_delimiter(sample: str) -> str:
    counts = {";": sample.count(";"), ",": sample.count(","), "\t": sample.count("\t")}
    delimiter = max(counts, key=counts.get)
    return delimiter if counts[delimiter] > 0 else ";"


def choose_fields(fieldnames: Iterable[str]) -> Tuple[Optional[str], Optional[str]]:
    fields = list(fieldnames or [])
    normalized = {name: normalize_header(name) for name in fields}

    number_field = next((name for name in fields if normalized[name] in NUMBER_HEADERS), None)
    name_field = next((name for name in fields if normalized[name] in NAME_HEADERS), None)

    if not number_field:
        for name in fields:
            key = normalized[name]
            if "kg" in key and ("nummer" in key or key.endswith("nr") or "code" in key):
                number_field = name
                break

    if not name_field:
        for name in fields:
            key = normalized[name]
            if "kg" in key and ("name" in key or "gemeinde" in key):
                name_field = name
                break

    return number_field, name_field


def parse_mapping_csv(csv_path: Path) -> Dict[str, str]:
    text = read_text_with_fallback(csv_path)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"CSV file is empty: {csv_path}")

    delimiter = pick_delimiter("\n".join(lines[:20]))
    reader = csv.DictReader(lines, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError(f"CSV header missing: {csv_path}")

    number_field, name_field = choose_fields(reader.fieldnames)
    if not number_field or not name_field:
        header_list = ", ".join(reader.fieldnames)
        raise ValueError(f"Could not find KG number/name columns in CSV header: {header_list}")

    mapping: Dict[str, str] = {}
    for row in reader:
        raw_number = (row.get(number_field) or "").strip()
        raw_name = (row.get(name_field) or "").strip()
        if not raw_number or not raw_name:
            continue

        digits = "".join(ch for ch in raw_number if ch.isdigit())
        if len(digits) != 5:
            continue

        clean_name = " ".join(raw_name.split())
        if digits not in mapping and clean_name:
            mapping[digits] = clean_name

    if not mapping:
        raise ValueError(f"No 5-digit KG mappings found in CSV: {csv_path}")

    return mapping


def score_name(name: str, keywords: Tuple[str, ...]) -> int:
    lower_name = name.lower()
    return sum(1 for keyword in keywords if keyword in lower_name)


def discover_files(root: Path) -> Tuple[Optional[Path], Optional[Path]]:
    csv_best: Optional[Tuple[int, int, Path]] = None
    zip_best: Optional[Tuple[int, int, Path]] = None

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = tuple(part.lower() for part in path.relative_to(root).parts)
        if "_kg_lookup_cache" in rel_parts:
            continue
        lower_name = path.name.lower()
        depth = len(path.relative_to(root).parts)

        if lower_name.endswith(".csv"):
            score = score_name(lower_name, CSV_KEYWORDS)
            if score > 0:
                candidate = (score, -depth, path)
                if csv_best is None or candidate > csv_best:
                    csv_best = candidate
        elif lower_name.endswith(".zip"):
            score = score_name(lower_name, ZIP_KEYWORDS)
            if score > 0:
                candidate = (score, -depth, path)
                if zip_best is None or candidate > zip_best:
                    zip_best = candidate

    csv_path = csv_best[2] if csv_best else None
    zip_path = zip_best[2] if zip_best else None
    return csv_path, zip_path


def extract_csv_from_zip(zip_path: Path, rawdata_root: Path) -> Path:
    del rawdata_root  # Kept in signature for compatibility with current call sites.
    cache_dir = Path(tempfile.gettempdir()) / "qfc_kg_lookup_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        csv_entries = [entry for entry in archive.infolist() if not entry.is_dir() and entry.filename.lower().endswith(".csv")]
        if not csv_entries:
            raise ValueError(f"ZIP file contains no CSV: {zip_path}")

        scored_entries = []
        for entry in csv_entries:
            entry_name = Path(entry.filename).name.lower()
            scored_entries.append((score_name(entry_name, CSV_KEYWORDS), len(entry.filename), entry))
        scored_entries.sort(reverse=True)
        best_entry = scored_entries[0][2]

        out_path = cache_dir / f"{zip_path.stem}_{Path(best_entry.filename).name}"
        with archive.open(best_entry) as source, out_path.open("wb") as target:
            target.write(source.read())
        return out_path


def resolve_mapping_source(rawdata_root: Path, explicit_mapping: Optional[str]) -> Tuple[Path, Optional[Path]]:
    if explicit_mapping:
        explicit_path = Path(explicit_mapping)
        if explicit_path.is_file():
            if explicit_path.suffix.lower() == ".zip":
                extracted = extract_csv_from_zip(explicit_path, rawdata_root)
                return extracted, explicit_path
            return explicit_path, None

    for name in CANDIDATE_FILENAMES:
        candidate = rawdata_root / name
        if candidate.is_file():
            return candidate, None

    csv_file, zip_file = discover_files(rawdata_root)
    if csv_file:
        return csv_file, None
    if zip_file:
        extracted = extract_csv_from_zip(zip_file, rawdata_root)
        return extracted, zip_file

    raise FileNotFoundError(f"No KG mapping CSV/ZIP found in rawdata root: {rawdata_root}")


def write_cache(cache_path: Path, mapping: Dict[str, str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8", newline="") as handle:
        for number in sorted(mapping):
            handle.write(f"{number};{mapping[number]}\n")


def write_status(status_path: Optional[Path], values: Dict[str, str]) -> None:
    if not status_path:
        return
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("w", encoding="utf-8", newline="") as handle:
        for key, value in values.items():
            clean = str(value).replace("\r", " ").replace("\n", " ")
            handle.write(f"{key}={clean}\n")


def clean_path_arg(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1]
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KG number->name lookup cache from local rawdata.")
    parser.add_argument("--rawdata-root", required=True, help="Rawdata folder to search for mapping CSV/ZIP.")
    parser.add_argument("--mapping-file", help="Optional explicit mapping file path (CSV or ZIP).")
    parser.add_argument("--cache-out", required=True, help="Output cache file path (semicolon separated).")
    parser.add_argument("--status-file", help="Optional status output file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status: Dict[str, str] = {}
    status_path = Path(clean_path_arg(args.status_file)) if args.status_file else None

    try:
        rawdata_root = Path(clean_path_arg(args.rawdata_root))
        if not rawdata_root.is_dir():
            raise FileNotFoundError(f"Rawdata root not found: {rawdata_root}")

        mapping_file = clean_path_arg(args.mapping_file) if args.mapping_file else None
        mapping_csv, extracted_from = resolve_mapping_source(rawdata_root, mapping_file)
        mapping = parse_mapping_csv(mapping_csv)
        write_cache(Path(clean_path_arg(args.cache_out)), mapping)

        status["MAPPING_FILE"] = str(mapping_csv)
        status["COUNT"] = str(len(mapping))
        if extracted_from:
            status["EXTRACTED_FROM"] = str(extracted_from)
        write_status(status_path, status)
        return 0
    except Exception as exc:
        status["ERROR"] = str(exc)
        write_status(status_path, status)
        return 1


if __name__ == "__main__":
    sys.exit(main())
