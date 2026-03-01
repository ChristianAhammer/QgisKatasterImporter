# 🚀 Quick Start Guide

## For QGIS Users (Easiest Way)

### 1. Install the Plugin (2 minutes)

**Windows Users - Automatic:**
```bash
bev_to_qfield_plugin\install_plugin.bat
```

**All Platforms - Manual:**
1. Copy `bev_to_qfield_plugin` folder
2. Paste into QGIS plugins directory:
   - **Windows**: `C:\Users\<YourUsername>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

### 2. Enable in QGIS (1 minute)

1. **Restart QGIS completely**
2. Go to **Plugins** → **Manage and Install Plugins**
3. Search for **"BEV to QField"**
4. ✓ Check the box to **Enable**
5. Close the dialog

### 3. Use It (5 minutes per conversion)

1. Go to **Vector** → **BEV to QField** → **Convert BEV Data to QField**
2. Choose your options:
   - ✓ **Create QField sync directory** (keep checked)
   - ✓ **Fix invalid geometries** (keep checked)
   - Other options as needed
3. Click **Start Conversion**
4. Monitor the progress log
5. Results appear in `03_QField_Output/`

## Before First Use

### Create Directory Structure
Create this folder at: `C:\Users\<YourUsername>\Meine Ablage (ca19770610@gmail.com)\QGIS\`

```
QGIS/
├── 01_BEV_Rawdata/         ← Place your input files here
├── 02_QGIS_Processing/
│   └── grids/              ← Optional NTv2 (.gsb) & geoid (.tif)
├── 03_QField_Output/       ← (created automatically)
└── 04_QField_Sync/         ← (created automatically)
```

### Add Your Data

1. Place BEV shapefiles/GeoPackages/GeoJSON in `01_BEV_Rawdata/`
2. *(Optional, recommended)* Place BEV `KG_Verzeichnis.zip` in `01_BEV_Rawdata/`
   - Enables KG number -> KG name display in CLI workflow
3. *(Optional)* Add NTv2 grid files to `02_QGIS_Processing/grids/`

## CLI Automation (Windows)

Use this mode when conversion + sync should run end-to-end from one script.

1. Ensure `qfieldcloud.env` exists in `02_QGIS_Processing/` and contains:
   - `QFC_OUTPUT_ROOT`
   - `QFC_SYNC_ROOT`
   - `QFIELDCLOUD_USERNAME` and/or `QFIELDCLOUD_TOKEN`
2. Run:

```batch
run_kataster_converter.bat
```

3. Enter a 5-digit KatastralGemeinde number (KG-Nr.), for example `51235`
4. Verify output in `03_QField_Output/kataster_<KG-Nr>_qfield/`
5. Verify sync copy in `04_QField_Sync/kataster_<KG-Nr>_qfield/`

## What You Get

After conversion, in `03_QField_Output/`:

| File | Use |
|------|-----|
| `kataster_*_qfield.gpkg` | Open in QGIS, ArcGIS, or QField |
| `kataster_*_qfield.qgz` | QGIS project (ready to use) |
| `kataster_*_qfield_report.txt` | Processing details |

## Troubleshooting

### Plugin doesn't show up
- Restart QGIS completely (not just close the window)
- Check QGIS version is 3.40+
- Check QGIS → View → Panels → Message Log for errors

### "No input data found"
- Put files in `01_BEV_Rawdata/` folder
- Supported formats: `.shp`, `.gpkg`, `.geojson`
- Make sure file extensions are correct

### Processing stops
- Check file permissions
- Ensure enough disk space (50% freespace recommended)
- Check QGIS Message Log (View → Panels → Message Log)

## Full Documentation

- **Plugin Guide**: See [bev_to_qfield_plugin/README.md](bev_to_qfield_plugin/README.md)
- **Technical Details**: See [README.md](README.md)

## Next Steps

1. ✓ Install plugin
2. ✓ Create directory structure
3. ✓ Add BEV data
4. ✓ Run conversion
5. ✓ Use output in QField or QGIS

---

**Questions?** See the [full plugin guide](bev_to_qfield_plugin/README.md) or report [issues on GitHub](https://github.com/ChristianAhammer/QgisKatasterImporter/issues)
