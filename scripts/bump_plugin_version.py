#!/usr/bin/env python3
"""Increment metadata.txt plugin version patch component."""

import configparser
from pathlib import Path


DEFAULT_METADATA_PATH = Path(__file__).resolve().parents[1] / "metadata.txt"


def parse_version(version):
    """Parse a version string and return (major, minor, patch)."""
    parts = version.strip().split(".")
    if len(parts) == 1 and parts[0].isdigit():
        return int(parts[0]), 0, 0
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        major, minor = map(int, parts)
        return major, minor, 0
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return tuple(map(int, parts))
    raise ValueError(f"Unsupported version format: {version}")


def bump_version(version):
    """Increment patch component of a version string."""
    major, minor, patch = parse_version(version)
    return f"{major}.{minor}.{patch + 1}"


def bump_metadata_version(metadata_path=DEFAULT_METADATA_PATH):
    """Bump [general]/version in metadata file and return new version."""
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(metadata_path, encoding="utf-8")

    if "general" not in config or "version" not in config["general"]:
        raise ValueError("metadata.txt is missing [general]/version")

    new_version = bump_version(config["general"]["version"])
    config["general"]["version"] = new_version

    with Path(metadata_path).open("w", encoding="utf-8", newline="\r\n") as handle:
        config.write(handle)

    return new_version


def main():
    try:
        print(bump_metadata_version())
    except ValueError as err:
        raise SystemExit(str(err)) from err


if __name__ == "__main__":
    main()
