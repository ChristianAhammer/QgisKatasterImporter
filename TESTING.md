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
  scripts/qgis_mcp_blackbox_check.py \
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

### 4) MCP black-box project check (optional)

This check validates generated output through the external QGIS MCP socket
boundary (no direct `qgis` imports in the test process).

Prerequisites:

- QGIS is running.
- `qgis_mcp` plugin is enabled.
- A generated project exists (for example in `03_QField_Output`).

Run:

```bash
python3 scripts/qgis_mcp_blackbox_check.py \
  --project "C:\Users\<YourUser>\Meine Ablage\QGIS\03_QField_Output\kataster_44106_qfield.qgz"
```

Windows wrapper:

```batch
run_mcp_blackbox_test.bat "C:\Users\<YourUser>\Meine Ablage\QGIS\03_QField_Output\kataster_44106_qfield.qgz"
```

Behavior:

- If MCP server is not reachable, the test asks you to start it in QGIS:
  `Plugins -> QGIS MCP -> QGIS MCP -> Start Server`
- After confirmation, it retries automatically.

Optional output summary:

```bash
python3 scripts/qgis_mcp_blackbox_check.py \
  --project "C:\Users\<YourUser>\Meine Ablage\QGIS\03_QField_Output\kataster_44106_qfield.qgz" \
  --summary-json scripts/_mcp_blackbox_summary.json
```

## Coverage Notes

- Unit tests provide deterministic coverage for QGIS-independent logic.
- QGIS-dependent conversion steps (Processing calls, CRS operations, project writing) remain integration-tested.
- MCP black-box check adds an external runtime probe across the plugin/socket boundary.
- For full end-to-end confidence, run both unit and QGIS integration tests before release.
