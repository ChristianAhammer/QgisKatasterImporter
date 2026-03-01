"""Shared path and filename helpers for Kataster conversion workflows.

These helpers are intentionally free of QGIS dependencies so they can be
covered by standard unit tests.
"""

import os
import re


_SOURCE_ROOT_PATTERN = re.compile(
    r"^(.*?)[\\/](?:01_bev_rawdata|01_bev_rohdaten)(?:[\\/].*)?$", flags=re.IGNORECASE
)
_TARGET_ROOT_PATTERN = re.compile(
    r"^(.*?)[\\/]03_qfield_output(?:[\\/].*)?$", flags=re.IGNORECASE
)
_KATASTER_SHP_PATTERN = re.compile(r"(?<![a-z])(gst|sgg)(?![a-z])")


def _canonical_path(value):
    # Use a slash literal in regex replacement to avoid Windows "\" escape issues,
    # then let normpath map to platform style.
    return os.path.normpath(re.sub(r"[\\/]+", "/", value))


def dedupe_paths(values):
    """Return normalized unique paths preserving first occurrence."""
    unique = []
    seen = set()
    for raw in values:
        if not raw:
            continue
        norm = _canonical_path(raw)
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(norm)
    return unique


def qgis_base_from_source(source_folder):
    """Return QGIS base folder inferred from 01_BEV_Rawdata/Rohdaten path."""
    folder_norm = _canonical_path(source_folder)
    match = _SOURCE_ROOT_PATTERN.search(folder_norm)
    if not match:
        return None
    return _canonical_path(match.group(1))


def qgis_base_from_target(target_gpkg):
    """Return QGIS base folder inferred from 03_QField_Output path."""
    target_norm = _canonical_path(target_gpkg)
    match = _TARGET_ROOT_PATTERN.search(target_norm)
    if not match:
        return None
    return _canonical_path(match.group(1))


def default_output_path(source_folder):
    """Build default output GPKG path for a source input folder."""
    folder_norm = _canonical_path(source_folder)
    folder_name = os.path.basename(folder_norm.rstrip(os.sep)) or "kataster_output"
    project_name = f"kataster_{folder_name}_qfield"

    match = _SOURCE_ROOT_PATTERN.search(folder_norm)
    if match:
        output_root = _canonical_path(
            os.path.join(match.group(1), "03_QField_Output", project_name)
        )
    else:
        output_root = _canonical_path(os.path.join(folder_norm, project_name))

    return _canonical_path(os.path.join(output_root, f"{project_name}.gpkg"))


def is_kataster_shapefile(filename):
    """Return True only for SHP files with GST/SGG token in base name."""
    lower = filename.lower()
    if not lower.endswith(".shp"):
        return False
    base = os.path.splitext(lower)[0]
    return _KATASTER_SHP_PATTERN.search(base) is not None


def path_action(existed_before, path, kind):
    """Build a normalized action descriptor for summary output."""
    if not path:
        return None
    action = "Aktualisiert" if existed_before else "Erstellt"
    return {"action": action, "kind": kind, "path": _canonical_path(path)}
