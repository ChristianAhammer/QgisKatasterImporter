#!/usr/bin/env python3
import configparser
from pathlib import Path

metadata_path = Path(__file__).resolve().parents[1] / "metadata.txt"
config = configparser.ConfigParser()
config.optionxform = str
config.read(metadata_path, encoding="utf-8")

if "general" not in config or "version" not in config["general"]:
    raise SystemExit("metadata.txt is missing [general]/version")

version = config["general"]["version"].strip()
parts = version.split('.')

if len(parts) == 1 and parts[0].isdigit():
    major, minor, patch = int(parts[0]), 0, 0
elif len(parts) == 2 and all(p.isdigit() for p in parts):
    major, minor = map(int, parts)
    patch = 0
elif len(parts) == 3 and all(p.isdigit() for p in parts):
    major, minor, patch = map(int, parts)
else:
    raise SystemExit(f"Unsupported version format: {version}")

patch += 1
new_version = f"{major}.{minor}.{patch}"
config["general"]["version"] = new_version

with metadata_path.open("w", encoding="utf-8", newline="\r\n") as f:
    config.write(f)

print(new_version)
