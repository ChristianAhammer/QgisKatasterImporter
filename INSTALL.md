# Installation Guide

## 🚀 Quick Install (Recommended)

### Windows Users

1. **Close QGIS completely** (if running)
2. **Double-click** `bev_to_qfield_plugin/install_plugin.bat`
3. **Restart QGIS**
4. **Enable the plugin**:
   - Go to **Plugins** → **Manage and Install Plugins**
   - Search for **"BEV to QField"**
   - ✓ Check the box to enable
   - Click **Close**
5. **Use it**: **Vector** → **BEV to QField** → **Convert BEV Data to QField**

### macOS / Linux

1. **Locate QGIS plugins directory**:
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. **Copy plugin folder**:
   ```bash
   cp -r bev_to_qfield_plugin/ <PLUGINS_DIRECTORY>/
   ```

3. **Restart QGIS**

4. **Enable in QGIS**: **Plugins** → **Manage and Install Plugins** → Search "BEV to QField" → Check to enable

---

## 🔧 Troubleshooting

### Error: "Module not found: bev_to_qfield"

**If you see this error when opening the plugin:**

```
ModuleNotFoundError: No module named 'bev_to_qfield'
```

**Fix:**

1. **Close QGIS completely** (check Task Manager to ensure it's fully closed)
2. **Run the fix script** (Windows):
   ```batch
   bev_to_qfield_plugin\fix_plugin_installation.bat
   ```
   - This reinstalls the plugin with all required modules
3. **Restart QGIS**
4. **Re-enable the plugin**: **Plugins** → **Manage and Install Plugins** → Search "BEV to QField" → ✓ Enable

### Plugin doesn't appear in menu

1. **Check QGIS version**: Must be **3.40 or later**
   - Check in **Help** → **About QGIS**

2. **Check if enabled**:
   - Go to **Plugins** → **Manage and Install Plugins**
   - Search for "BEV to QField"
   - Ensure the checkbox is ✓ checked

3. **Check Message Log**:
   - **View** → **Panels** → **Message Log**
   - Look for error messages with "BEVToQField"
   - Report any error message on GitHub

4. **Reinstall**:
   - Windows: Run `bev_to_qfield_plugin/fix_plugin_installation.bat`
   - Other: Manually remove plugin folder and copy again

### "No input data found"

1. **Create directory structure**:
   ```
   C:\Users\<YourUsername>\Meine Ablage\QGIS\
   ├── 01_BEV_Rohdaten/           ← Add your files here
   ├── 02_QGIS_Processing/
   │   └── grids/
   ├── 03_QField_Output/
   └── 04_QField_Sync/
   ```

2. **Add your data**:
   - Place Shapefiles (.shp), GeoPackages (.gpkg), or GeoJSON files in `01_BEV_Rohdaten/`
   - Ensure file extensions are correct

3. **Verify file formats**:
   - Supported: `.shp`, `.gpkg`, `.geojson`
   - All files must have proper CRS (EPSG:31255 for BEV data)

---

## 📋 Manual Installation (Advanced)

### All Platforms

1. **Locate QGIS plugins directory**:
   - **Windows**: `C:\Users\<YourUsername>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. **Copy plugin folder**:
   ```bash
   # Copy the entire bev_to_qfield_plugin folder to your plugins directory
   cp -r bev_to_qfield_plugin/ <PLUGINS_DIRECTORY>/
   ```

3. **Verify contents** - The plugin directory should contain:
   ```
   bev_to_qfield_plugin/
   ├── __init__.py
   ├── bev_to_qfield.py
   ├── bev_to_qfield_plugin.py
   ├── bev_converter.py
   ├── metadata.txt
   └── install_plugin.bat
   ```

4. **Restart QGIS entirely** (not just closing the window)

5. **Enable plugin**:
   - **Plugins** → **Manage and Install Plugins**
   - Search for "BEV to QField"
   - ✓ Check to enable
   - Click **Close**

---

## 🧪 Verify Installation

After installing, verify the plugin works:

1. **Open QGIS**
2. **Check plugin menu**: **Vector** → **BEV to QField**
   - Should see two options:
     - **Convert BEV Data to QField** ← Main converter
     - **About BEV to QField** ← Information

3. **Click "Convert BEV Data to QField"**
   - A dialog should appear with options
   - No errors in QGIS Message Log

4. **Test with sample data** (optional):
   - Create `01_BEV_Rohdaten/` folder
   - Add a test Shapefile
   - Run conversion to verify

---

## ✅ What Should Happen

### After Installation

- Plugin appears in **Vector** menu
- No error messages in QGIS Message Log
- Can open the converter dialog without errors

### After First Run

- Output folder structure created automatically
- Files processed and converted
- New QGIS project created with styled layers
- Processing report generated

---

## 🆘 Need Help?

### Check These Resources

- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Plugin Guide**: [bev_to_qfield_plugin/README.md](bev_to_qfield_plugin/README.md)
- **Main README**: [README.md](README.md)

### Report Issues

1. **Check QGIS Message Log**:
   - **View** → **Panels** → **Message Log**
   - Copy any error messages

2. **Report on GitHub**:
   - Go to [Issues](https://github.com/ChristianAhammer/QgisKatasterImporter/issues)
   - Include:
     - QGIS version (Help → About QGIS)
     - Python version
     - Error message or screenshot
     - Steps to reproduce

---

## 📦 Uninstall

### Windows

```batch
rmdir /s C:\Users\<YourUsername>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\bev_to_qfield_plugin
```

Then restart QGIS.

### macOS / Linux

```bash
rm -rf ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/bev_to_qfield_plugin/
# For Linux:
rm -rf ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/bev_to_qfield_plugin/
```

Then restart QGIS.

---

## 💡 Tips

- **Keep plugins updated**: Check GitHub releases for updates
- **Backup your data**: Always backup input files before processing
- **Use NTv2 grids**: Place `.gsb` files in `02_QGIS_Processing/grids/` for accurate transformation
- **Check logs**: Processing report in output folder has all details

---

**Ready? Start with [QUICKSTART.md](QUICKSTART.md)!**
