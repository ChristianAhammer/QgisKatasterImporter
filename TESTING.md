# Testing Guide

## Test Layers

### 1) Unit tests (no QGIS required)

Run from repository root:

```bash
python3 -m unittest -v \
  test_kataster_common.py \
  test_bump_plugin_version.py \
  test_kg_mapping_lookup.py \
  test_qgis_mcp_blackbox_check.py
```

Covered areas:

- Shared path and naming helpers in `kataster_common.py`
- Version parsing and metadata update logic in `scripts/bump_plugin_version.py`
- KG mapping discovery/parsing logic in `scripts/kg_mapping_lookup.py`
- MCP socket client helpers in `scripts/qgis_mcp_blackbox_check.py`
- Socket-dependent MCP helper unit tests auto-skip in restricted environments
  where socket creation is blocked by sandbox policy.

### 2) Syntax validation

```bash
python3 -m py_compile \
  kataster_converter.py \
  scripts/kataster_converter_cli.py \
  scripts/kg_mapping_lookup.py \
  scripts/qgis_mcp_blackbox_check.py \
  scripts/bump_plugin_version.py \
  bev_to_qfield.py \
  bev_to_qfield_plugin/bev_to_qfield.py \
  bev_to_qfield_plugin/bev_converter.py \
  bev_to_qfield_plugin/bev_to_qfield_plugin.py \
  test_qgis_integration.py \
  test_kg_mapping_lookup.py \
  test_qgis_mcp_blackbox_check.py
```

### 3) QGIS integration test (OSGeo4W / Windows)

Requires QGIS Python (`qgis` module) to be available.

```batch
run_qgis_test.bat
```

If `qgis` is not installed in the active environment, this test will fail early with:
`No module named 'qgis'`.

### 4) MCP black-box project check (manual mode)

This check validates generated output through the external QGIS MCP socket
boundary (no direct `qgis` imports in the test process).

Prerequisites:

- QGIS is running.
- `qgis_mcp` plugin is enabled.
- A generated project exists (for example in `03_QField_Output`).

Run:

```bash
python3 scripts/qgis_mcp_blackbox_check.py \
  --project "C:\Users\<YourUser>\Meine Ablage\bev-qfield-workbench-data\03_QField_Output\kataster_44106_qfield.qgz"
```

Windows wrapper:

```batch
run_mcp_blackbox_test.bat "C:\Users\<YourUser>\Meine Ablage\bev-qfield-workbench-data\03_QField_Output\kataster_44106_qfield.qgz"
```

Behavior:

- If MCP server is not reachable, the test asks you to start it in QGIS:
  `Plugins -> QGIS MCP -> QGIS MCP -> Start Server`
- After confirmation, it retries automatically.

### 5) MCP integration test (automatic mode, recommended)

This wrapper performs the full two-step flow automatically:

1. Start QGIS (if MCP is not already reachable)
2. Run `scripts/qgis_mcp_autostart.py` via `--code` to start MCP server
3. Wait for MCP port `9876`
4. Run `scripts/qgis_mcp_blackbox_check.py`

Run:

```batch
run_mcp_integration_test.bat "C:\Users\<YourUser>\Meine Ablage\bev-qfield-workbench-data\03_QField_Output\kataster_44106_qfield\kataster_44106_qfield.qgz"
```

Optional:

- Set `QFC_MCP_WAIT_SECONDS` to override startup wait timeout (default: `90`).
- Set `QFC_MCP_KEEP_QGIS=1` to keep the auto-started QGIS instance open after test completion.

Optional output summary:

```bash
python3 scripts/qgis_mcp_blackbox_check.py \
  --project "C:\Users\<YourUser>\Meine Ablage\bev-qfield-workbench-data\03_QField_Output\kataster_44106_qfield.qgz" \
  --summary-json scripts/_mcp_blackbox_summary.json
```

## Coverage Notes

- Unit tests provide deterministic coverage for QGIS-independent logic.
- QGIS-dependent conversion steps (Processing calls, CRS operations, project writing) remain integration-tested.
- MCP black-box check adds an external runtime probe across the plugin/socket boundary.
- `run_mcp_integration_test.bat` is the permanent end-to-end MCP integration test entrypoint.
- For full end-to-end confidence, run both unit and QGIS integration tests before release.
