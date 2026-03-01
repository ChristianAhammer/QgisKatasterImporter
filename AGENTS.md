# Codex Startup Prompt

Use this file as first context after a session restart.

## Project Goal

Convert BEV cadastral raw data (5-digit KatastralGemeinde number) into QField-ready output and sync via CLI.

## Start Here

1. Check repo state: `git status --short`
2. Review workflow entrypoint: `run_kataster_converter.bat`
3. Review tests/docs: `TESTING.md`
4. For MCP integration tests:
   - Preferred (auto-start): `run_mcp_integration_test.bat`
   - Manual mode: `run_mcp_blackbox_test.bat` and `scripts/qgis_mcp_blackbox_check.py`
   - Set `QFC_MCP_KEEP_QGIS=1` only when QGIS should stay open after auto-start test runs.

## Environment Facts

- Repository location: `C:\GitRepos\bev-qfield-workbench`
- Previous location `C:\Users\Christian\GitRepos` may exist as a junction.
- QGIS Python launcher is expected under `C:\OSGeo4W\...`.
- Main config file is usually:
  `C:\Users\Christian\Meine Ablage (ca19770610@gmail.com)\QGIS\02_QGIS_Processing\qfieldcloud.env`

## Workflow Rules

- Keep cloud sync automation in CLI/batch workflow.
- Do not assume the QGIS plugin should auto-push to cloud.
- Prefer Windows-side execution for batch/QGIS tasks (`cmd.exe /c ...`).

## WSL + Windows Limitations (Important)

- Running `cmd.exe` from WSL starts in a UNC path that can break commands.
- In every Windows command, first switch to drive/path:
  `cd /d C:\GitRepos\bev-qfield-workbench`
- Be careful with quoting when paths contain spaces and parentheses.
- Prefer backslashes for Windows `if exist` checks.

## KG Number -> Name Lookup

- `run_kataster_converter.bat` now tries to show KG names for 5-digit folders/selections.
- Mapping source can be:
  - CSV/ZIP in rawdata root
  - explicit `QFC_KG_MAPPING_FILE` in `qfieldcloud.env`
- Resolver script: `scripts/kg_mapping_lookup.py`
- If mapping is missing, workflow continues and prints a note.

## Data/Artifact Hygiene

- Summary files in `scripts/_sync_*_summary.json` are run artifacts.
- Do not remove unrelated user changes.
- Avoid committing local secrets/config values.
