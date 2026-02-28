# BEV to QField Converter - QGIS Plugin

Convert Austrian cadastral data from BEV format (MGI/Gauß-Krüger EPSG:31255) to ETRS89/UTM33N (EPSG:25833) for QField mobile fieldwork.

## Installation

### Option 1: Automatic Installation (Recommended)

1. **Open QGIS** (3.40 or later)
2. Go to **Plugins** → **Manage and Install Plugins...**
3. Search for **"BEV to QField"**
4. Click **Install**
5. Enable the plugin in the Installed tab

### Option 2: Manual Installation

1. **Locate QGIS Plugins Directory:**
   - **Windows**: `C:\Users\<YourUsername>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`
   - **macOS**: `~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins`

2. **Copy the plugin:**
   ```bash
   git clone https://github.com/ChristianAhammer/QgisKatasterImporter.git
   cp -r QgisKatasterImporter/bev_to_qfield_plugin/ <PLUGINS_DIRECTORY>/bev_to_qfield_plugin
   ```

3. **Restart QGIS** and enable the plugin via **Plugins** → **Manage and Install Plugins**

### Option 3: Development Installation

For development and testing:

```bash
cd <PLUGINS_DIRECTORY>
git clone https://github.com/ChristianAhammer/QgisKatasterImporter.git bev_to_qfield_plugin
```

## Setup

### Directory Structure

The plugin expects the following directory structure in your QGIS folder:

```
C:\Users\<YourUsername>\Meine Ablage (ca19770610@gmail.com)\QGIS\
├── 01_BEV_Rohdaten/               # ← Place your input BEV data here
├── 02_QGIS_Processing/
│   └── grids/                     # ← Optional NTv2 (.gsb) and geoid grids (.tif)
├── 03_QField_Output/              # ← Generated output files
├── 04_QField_Sync/                # ← QField sync folder
```

You can create this structure manually or let the plugin create it for you.

### Optional: NTv2 Grid & Geoid Grid

For more accurate coordinate transformation and orthometric heights:

1. **Download NTv2 Grid:**
   - Austrian NTv2 grid from [BEV (Österreichisches Bundesamt für Eich- und Vermessungswesen)](https://www.bev.gv.at/)
   - Place in: `02_QGIS_Processing/grids/` with extension `.gsb`

2. **Download Geoid Grid:**
   - Austrian geoid height grid
   - Place in: `02_QGIS_Processing/grids/` with pattern name `GV_Hoehengrid*.tif`

## Usage

### From QGIS Interface

1. **Open QGIS** and go to **Vector** → **BEV to QField** → **Convert BEV Data to QField**

2. **Configure Options:**
   - ✓ **Create QField sync directory** - Prepares folder structure for mobile sync
   - **Clean sync directory** - Removes old files before processing
   - **Open QGIS project on completion** - Automatically opens the result
   - ✓ **Fix invalid geometries** - Repairs invalid shapes before conversion

3. **Click "Start Conversion"** and monitor the processing log

4. **Review output:**
   - `kataster_<FOLDERNAME>_qfield.gpkg` - GeoPackage with all layers
   - `kataster_<FOLDERNAME>_qfield.qgz` - Styled QGIS project
   - `kataster_<FOLDERNAME>_qfield_report.txt` - Processing report
   - Archive copies in `03_QField_Output/archive/`

### From Command Line

```bash
# Using OSGeo4W Python
cd path/to/QgisKatasterImporter
C:\OSGeo4W\bin\o4w_env.bat
python bev_to_qfield.py
```

## Output Files

### GeoPackage Database
- Single file containing all transformed layers
- Compatible with QGIS, QField, and other GIS applications
- Preserves all original attributes

### QGIS Project (.qgz)
- Pre-configured map with:
  - All cadastral layers with styling
  - Polygon layers: transparent fill with black outline
  - BEV orthofoto base layer (basemap.at WMTS)
  - CRS set to ETRS89/UTM33N

### QField Sync Directory
- Ready for QField data synchronization
- Project configuration for offline fieldwork
- Automatic layer packaging for mobile devices

### Processing Report
- Detailed log of transformation parameters
- CRS information (source and target)
- NTv2/geoid grid usage
- List of processed layers

## Features

✓ **Batch Processing** - Convert multiple layers at once
✓ **NTv2 Support** - Optional grid-based transformation for accuracy
✓ **Geoid Heights** - Orthometric height calculation
✓ **Auto-Styling** - Styled polygon layers with transparency
✓ **Basemap Integration** - BEV orthofoto WMTS layer
✓ **QField Ready** - Direct integration with mobile fieldwork
✓ **Report Generation** - Detailed processing documentation
✓ **Progress Tracking** - Real-time feedback in QGIS

## Supported Input Formats

- Shapefiles (.shp)
- GeoPackage (.gpkg)
- GeoJSON (.geojson)

## Coordinate Reference Systems

| Stage | CRS | EPSG Code | Description |
|-------|-----|-----------|-------------|
| Input | MGI/Gauß-Krüger | EPSG:31255 | Austrian cadastral system |
| Output | ETRS89/UTM33N | EPSG:25833 | European standard for Austria |

## Requirements

- **QGIS**: 3.40 or later
- **Python**: 3.7+
- **PyQt5**
- **OSGeo4W** (Windows, optional - for standalone CLI usage)

## Troubleshooting

### Plugin doesn't appear in QGIS
1. Check that the plugin directory contains all required files: `metadata.txt`, `__init__.py`, `bev_to_qfield_plugin.py`
2. Check QGIS message log: **View** → **Panels** → **Message Log**
3. Verify QGIS version is 3.40+

### "No input data found"
1. Ensure input folder exists: `01_BEV_Rohdaten/`
2. Place valid shape files, GeoPackages, or GeoJSON files in it
3. Check file extensions are correct (.shp, .gpkg, .geojson)

### CRS not recognized
1. Verify layer has proper CRS set (should be EPSG:31255)
2. Check QGIS CRS database is up to date
3. Run QGIS with `--noplugins` flag to reset cache if needed

### Conversion is slow
- Large datasets (>100MB) may take time
- NTv2 transformation adds 15-20% processing time
- Check system resources (RAM, disk space)

## Support

- **Issues**: [GitHub Issues](https://github.com/ChristianAhammer/QgisKatasterImporter/issues)
- **Repository**: [GitHub Repository](https://github.com/ChristianAhammer/QgisKatasterImporter)

## License

Same as QGIS - [GPLv2+](http://www.gnu.org/licenses/gpl-2.0.html)

## Author

Christian Ahammer
- Email: ca19770610@gmail.com
- GitHub: [@ChristianAhammer](https://github.com/ChristianAhammer)

## Changelog

### Version 1.0.0 (February 2026)
- Initial release
- Class-based refactored architecture
- Full QGIS 3.44.0 integration
- Processing provider integration
- Menu-based UI
- Real-time progress feedback
- Comprehensive testing suite
