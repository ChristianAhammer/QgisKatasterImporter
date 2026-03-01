# Quality Criteria

## Baseline Checks

- `python3 -m py_compile ...` passes for core scripts and plugin modules.
- Unit tests pass without QGIS runtime.
- QGIS integration test passes in OSGeo4W environment.
- Documentation links in `README.md` resolve to existing files.

## Release Checklist

1. Run unit tests from `TESTING.md`.
2. Run QGIS integration test on Windows/OSGeo4W.
3. Verify `metadata.txt` version bump (pre-commit hook triggers `scripts/bump_plugin_version.py`).
4. Check converter output artifacts:
   - `*.gpkg`
   - `*.qgz`
   - `*_report.txt`
5. Validate plugin menu/action visibility in QGIS.

## Known Constraints

- Continuous integration is not available inside the QGIS runtime by default.
- Full behavioral validation still requires a local QGIS installation and representative cadastral input data.
