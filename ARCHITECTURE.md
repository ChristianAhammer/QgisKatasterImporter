# Architecture

## Overview

The repository contains two converter implementations and one plugin UI:

- `kataster_converter.py`: QGIS plugin action for converting GST/SGG SHP files into a target GeoPackage and QGIS project.
- `scripts/kataster_converter_cli.py`: headless PyQGIS CLI with JSON-capable summary output.
- `bev_to_qfield.py` and `bev_to_qfield_plugin/*`: class-based converter plus dedicated plugin UI workflow.
- `kataster_common.py`: shared pure-Python helper functions used by both GUI and CLI converter code paths.

## Runtime Flows

### QGIS plugin flow (`kataster_converter.py`)
1. User picks source folder (and optional target GPKG if project is unsaved).
2. Converter resolves required GIS grid (`*.gsb`) and validates active transformation operation.
3. GST/SGG SHP layers are reprojected to EPSG:25833 and written to a GeoPackage.
4. Output `.qgz`, report text file, and optional archive copies are created.

### CLI flow (`scripts/kataster_converter_cli.py`)
1. CLI boots QGIS + Processing environment.
2. Same conversion pipeline as plugin path, but non-interactive.
3. Writes summary to stdout and optional JSON output.

## Shared Utility Layer

`kataster_common.py` centralizes stable utility logic:

- Path normalization and deduplication (`dedupe_paths`)
- QGIS base path inference from source/target paths
- Default output file path generation
- SHP filename filter (`gst`/`sgg` token logic)
- Path action metadata for run summaries

The utility layer is intentionally QGIS-independent so it can be unit-tested without OSGeo4W/QGIS.

## Quality Boundaries

- QGIS-dependent behavior is validated through integration tests.
- Non-QGIS logic is validated by standard-library unit tests.
- Version bump automation (`scripts/bump_plugin_version.py`) is isolated as pure functions and covered by unit tests.
