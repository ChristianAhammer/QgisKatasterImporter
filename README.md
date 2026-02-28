# QgisKatasterImporter

Convert Austrian cadastral data (BEV - Bundesamt für Eich- und Vermessungswesen) from MGI/Gauß-Krüger to ETRS89/UTM33N and prepare for QField mobile fieldwork.

![License](https://img.shields.io/badge/License-GPLv2+-blue)
![QGIS](https://img.shields.io/badge/QGIS-3.40+-green)
![Python](https://img.shields.io/badge/Python-3.7+-blue)

## 🚀 Quick Start

### Option 1: QGIS Plugin (Recommended for QGIS Users)

**Easiest method - runs directly in QGIS with a graphical interface:**

1. Install QGIS 3.40 or later
2. Double-click `bev_to_qfield_plugin/install_plugin.bat` (Windows)
   - Or manually copy `bev_to_qfield_plugin` to QGIS plugins directory
3. Restart QGIS
4. Enable plugin: **Plugins** → **Manage and Install Plugins** → Search "BEV to QField"
5. Use: **Vector** → **BEV to QField** → **Convert BEV Data to QField**

**See [bev_to_qfield_plugin/README.md](bev_to_qfield_plugin/README.md) for detailed documentation.**

### Option 2: Standalone Script (Command Line)

**For automation, scripting, or non-QGIS environments:**

```bash
# Setup environment
set OSGEO4W_ROOT=C:\OSGeo4W
call %OSGEO4W_ROOT%\bin\o4w_env.bat

# Run converter
python bev_to_qfield.py
```

## 📋 Features

✅ **Batch Processing** - Convert multiple vector layers at once
✅ **Accurate Transformation** - Optional NTv2 grid-based coordinate shift
✅ **Orthometric Heights** - Calculate heights using geoid grid
✅ **Automatic Styling** - Styled polygon layers with transparency
✅ **Basemap Integration** - BEV orthofoto (basemap.at) WMTS layer
✅ **QField Ready** - Direct output for mobile fieldwork apps
✅ **Report Generation** - Detailed processing documentation
✅ **Progress Tracking** - Real-time feedback during processing

## 🗺️ What Does It Do?

```
Input:  Austrian BEV Cadastral Data (MGI/GK - EPSG:31255)
         ↓
      [Fix Geometries] → [Coordinate Transform] → [Geoid Heights]
         ↓
Output: ETRS89/UTM33N (EPSG:25833) ready for QField
         - GeoPackage database (.gpkg)
         - QGIS project (.qgz)
         - QField sync structure
         - Processing report
```

## 📦 Supported Input Formats

- Shapefiles (.shp)
- GeoPackage (.gpkg)
- GeoJSON (.geojson)

## 💾 Output Files

| File | Purpose |
|------|---------|
| `kataster_*_qfield.gpkg` | GeoPackage with all transformed layers |
| `kataster_*_qfield.qgz` | Pre-styled QGIS project with basemap |
| `kataster_*_qfield_report.txt` | Processing parameters and layer list |
| `04_QField_Sync/` | Directory structure for mobile sync |

## 📁 Directory Structure

```
C:\Users\<YourUser>\Meine Ablage\QGIS\
├── 01_BEV_Rohdaten/           ← Input BEV data
├── 02_QGIS_Processing/
│   └── grids/                 ← Optional NTv2 (.gsb) & geoid (.tif)
├── 03_QField_Output/          ← Generated output
│   └── archive/               ← Timestamped backups
└── 04_QField_Sync/            ← QField sync folder
```

## 🔧 Installation Methods

### QGIS Plugin (Windows)
```batch
cd bev_to_qfield_plugin
install_plugin.bat
```

### QGIS Plugin (Manual - All Platforms)
Copy `bev_to_qfield_plugin/` folder to:
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

### Development Installation
```bash
git clone https://github.com/ChristianAhammer/QgisKatasterImporter.git
cd QgisKatasterImporter/bev_to_qfield_plugin
# Copy to QGIS plugins directory
```

## ✅ Testing

### Integration Test (QGIS with OSGeo4W)
```batch
cd bev_to_qfield_plugin
run_qgis_test.bat
```

All tests should pass ✓

## 🏗️ Architecture

The refactored codebase uses a class-based design:

```python
# Configuration encapsulation
config = BEVToQFieldConfig(base_path)
config.MAKE_SYNC_DIR = True
config.CLEAN_SYNC_DIR = False
config.FIX_GEOM = True

# Main converter
converter = BEVToQField(config)
converter.run()  # Interactive UI will prompt for input folder
```

### Key Classes

- **BEVToQFieldConfig**: Settings & directory management
- **BEVToQField**: Main conversion logic with helper methods
- **BEVToQFieldPlugin**: QGIS integration point
- **BEVToQFieldDialog**: User interface for QGIS
- **ConverterWorkerThread**: Background processing thread

## 📚 Documentation

- **[Plugin Installation & Usage](bev_to_qfield_plugin/README.md)** - Full plugin guide
- **[Architecture & Optimization](ARCHITECTURE.md)** - Technical details
- **[Testing Guide](TESTING.md)** - Test suite documentation

## 🔗 Coordinate Systems

| Stage | CRS | Code | Description |
|-------|-----|------|-------------|
| Input | MGI/Gauß-Krüger | EPSG:31255 | Austrian land register |
| Output | ETRS89/UTM33N | EPSG:25833 | European standard |

Optional: NTv2 grid + geoid heights for maximum accuracy

## 📋 Requirements

- **QGIS**: 3.40 or later
- **Python**: 3.7 or later
- **PyQt5**: Included with QGIS
- **OSGeo4W**: For Windows standalone usage
- **Internet**: For basemap.at WMTS layer

## 🐛 Troubleshooting

### Plugin not visible in QGIS
1. Check [plugin README](bev_to_qfield_plugin/README.md) Troubleshooting section
2. Verify QGIS version is 3.40+
3. Check QGIS Message Log for errors

### Coordinate transformation issues
1. Ensure input data has CRS set to EPSG:31255
2. Place NTv2 grid (.gsb) in `02_QGIS_Processing/grids/`
3. Check QGIS CRS database is up to date

### Slow processing
- Large datasets (>500MB) may take time
- NTv2 adds 15-20% overhead
- Check available RAM and disk space

See [plugin README](bev_to_qfield_plugin/README.md) for more troubleshooting.

## 📄 License

GPLv2+ - Same as QGIS

## 👤 Author

**Christian Ahammer**
- Email: ca19770610@gmail.com
- GitHub: [@ChristianAhammer](https://github.com/ChristianAhammer)

## 🔄 Version History

### v1.0.0 (Feb 2026)
- ✨ Initial release
- 🏗️ Class-based refactored architecture
- ✅ Full QGIS 3.44.0 integration
- 🎨 QGIS plugin UI with real-time feedback
- 📝 Comprehensive test suite
- 📖 Complete documentation

## 🙏 Acknowledgments

- BEV (Österreichisches Bundesamt für Eich- und Vermessungswesen)
- basemap.at for orthofoto tiles
- QGIS community for excellent GIS framework

## 📞 Support

- **GitHub Issues**: [Report issues here](https://github.com/ChristianAhammer/QgisKatasterImporter/issues)
- **GitHub Discussions**: [Ask questions here](https://github.com/ChristianAhammer/QgisKatasterImporter/discussions)

---

**Ready to use? Start with the [QGIS Plugin Installation Guide](bev_to_qfield_plugin/README.md)!**
