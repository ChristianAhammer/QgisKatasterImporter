# Testing Guide

## Test Layers

### 1) Unit tests (no QGIS required)

Run from repository root:

```bash
python3 -m unittest -v test_kataster_common.py test_bump_plugin_version.py
```

Covered areas:

- Shared path and naming helpers in `kataster_common.py`
- Version parsing and metadata update logic in `scripts/bump_plugin_version.py`

### 2) Syntax validation

```bash
python3 -m py_compile \
  kataster_converter.py \
  scripts/kataster_converter_cli.py \
  scripts/bump_plugin_version.py \
  bev_to_qfield.py \
  bev_to_qfield_plugin/bev_to_qfield.py \
  bev_to_qfield_plugin/bev_converter.py \
  bev_to_qfield_plugin/bev_to_qfield_plugin.py \
  test_qgis_integration.py
```

### 3) QGIS integration test (OSGeo4W / Windows)

Requires QGIS Python (`qgis` module) to be available.

```batch
run_qgis_test.bat
```

If `qgis` is not installed in the active environment, this test will fail early with:
`No module named 'qgis'`.

## Coverage Notes

- Unit tests provide deterministic coverage for QGIS-independent logic.
- QGIS-dependent conversion steps (Processing calls, CRS operations, project writing) remain integration-tested.
- For full end-to-end confidence, run both unit and QGIS integration tests before release.
