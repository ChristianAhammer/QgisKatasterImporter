# bev_to_qfield.py — QGIS 3.44.x
# BEV (MGI/GK) → ETRS89 / UTM33N (EPSG:25833) + optionale Geoid-Höhen
import os, sys, glob, datetime, shutil, tempfile
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# ---------- Bootstrap für QGIS + Processing ----------
QGIS_PREFIX = os.environ.get("QGIS_PREFIX_PATH", r"C:\OSGeo4W\apps\qgis")
QGIS_PY     = os.path.join(QGIS_PREFIX, "python")
QGIS_PLUG   = os.path.join(QGIS_PY, "plugins")
for p in (QGIS_PY, QGIS_PLUG):
    if p not in sys.path:
        sys.path.append(p)

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsCoordinateReferenceSystem, QgsVectorFileWriter,
    QgsCoordinateTransformContext, QgsProviderRegistry,
    QgsWkbTypes, QgsProcessingFeedback,
    QgsFillSymbol, QgsSingleSymbolRenderer
)

from PyQt5.QtWidgets import QFileDialog
import processing
from processing.core.Processing import Processing

# Initialize QGIS application
# If running as plugin, QgsApplication already exists and is initialized
# If running standalone, we need to create and initialize it
_qgs_app = QgsApplication.instance()
_qgs_app_is_standalone = False  # Track if we created the app ourselves

if _qgs_app is None:
    # Standalone mode - create and initialize QgsApplication
    QgsApplication.setPrefixPath(QGIS_PREFIX, True)
    _qgs_app = QgsApplication([], True)
    _qgs_app.initQgis()
    Processing.initialize()
    _qgs_app_is_standalone = True
# else: Plugin mode - QGIS handles all initialization

# ---------- Constants ----------
INPUT_PATTERNS = ("*.shp", "*.gpkg", "*.geojson")
SRC_CRS_CODE = "EPSG:31255"
TGT_CRS_CODE = "EPSG:25833"
TEMP_GPKG_NAME = "kataster_qfield_tmp.gpkg"
WMTS_LAYER_NAME = "BEV Orthofoto (basemap.at)"
GEOID_PATTERN_NAME = "GV_Hoehengrid*.tif"

# ---------- Configuration Class ----------
class BEVToQFieldConfig:
    """Configuration and settings for BEV to QField conversion."""
    
    # Feature flags
    MAKE_SYNC_DIR = True
    CLEAN_SYNC_DIR = False
    OPEN_QGIS_ON_FINISH = False
    FIX_GEOM = True
    
    # CRS settings
    SRC_CRS = SRC_CRS_CODE
    TGT_CRS = TGT_CRS_CODE
    
    def __init__(self, base_path: str):
        self.base = Path(base_path)
        self.dir_proc = self.base / "02_QGIS_Processing"
        self.dir_grids = self.dir_proc / "grids"
        self.dir_out = self.base / "03_QField_Output"
        self.dir_arch = self.dir_out / "archive"
        
        local_temp_root = Path(os.environ.get("LOCALAPPDATA", r"C:\Temp")) / "QGIS_Work"
        local_temp_root.mkdir(parents=True, exist_ok=True)
        self.run_temp_dir = Path(tempfile.mkdtemp(prefix="bev2qfield_", dir=str(local_temp_root)))
    
    def ensure_dirs(self):
        """Ensure all required directories exist."""
        for d in (self.dir_grids, self.dir_out, self.dir_arch, self.run_temp_dir):
            d.mkdir(parents=True, exist_ok=True)


# ---------- Main Processing Class ----------
class BEVToQField:
    """Main converter from BEV cadastral data to QField format."""
    
    def __init__(self, config: BEVToQFieldConfig):
        self.config = config
        self.feedback = QgsProcessingFeedback()
        self.target_crs = QgsCoordinateReferenceSystem(config.TGT_CRS)
        self.transform_ctx = QgsProject.instance().transformContext()
        self.layer_cache: Dict[str, QgsVectorLayer] = {}
        self.written_layers: List[str] = []
    
    def log(self, msg: str):
        """Log message with timestamp."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[bev2qfield {ts}] {msg}", flush=True)
    
    def _safe_name(self, name: str) -> str:
        """Convert name to safe layer name."""
        return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)[:60]
    
    def _find_ntv2_grid(self) -> Optional[str]:
        """Find NTv2 grid file."""
        cands = sorted(glob.glob(os.path.join(self.config.dir_grids, "**", "*.gsb"), recursive=True))
        return cands[0].replace("\\", "/") if cands else None
    
    def _find_geoid(self) -> Optional[str]:
        """Find geoid height grid file."""
        cands = sorted(glob.glob(os.path.join(self.config.dir_grids, "**", GEOID_PATTERN_NAME), recursive=True))
        return cands[0] if cands else None
    
    def _is_valid_layer(self, lyr: QgsVectorLayer) -> bool:
        """Check if layer is valid and has geometry."""
        if not lyr.isValid():
            return False
        wkt = lyr.wkbType()
        return QgsWkbTypes.geometryType(wkt) != QgsWkbTypes.UnknownGeometry
    
    def _ensure_crs(self, lyr: QgsVectorLayer) -> QgsVectorLayer:
        """Ensure layer has valid source CRS."""
        if not lyr.crs().isValid():
            lyr.setCrs(QgsCoordinateReferenceSystem(self.config.SRC_CRS))
        return lyr
    
    def collect_layers(self, dir_raw: str) -> List[QgsVectorLayer]:
        """Collect and validate input layers from directory."""
        files = []
        for pat in INPUT_PATTERNS:
            files.extend(glob.glob(os.path.join(dir_raw, "**", pat), recursive=True))
        
        layers = []
        for p in files:
            lyr = QgsVectorLayer(p, os.path.splitext(os.path.basename(p))[0], "ogr")
            if self._is_valid_layer(lyr):
                layers.append(lyr)
        return layers
    
    def _fix_geometries(self, lyr: QgsVectorLayer) -> QgsVectorLayer:
        """Fix invalid geometries if enabled."""
        if not self.config.FIX_GEOM or QgsWkbTypes.geometryType(lyr.wkbType()) == QgsWkbTypes.UnknownGeometry:
            return lyr
        
        result = processing.run(
            "native:fixgeometries",
            {"INPUT": lyr, "METHOD": 0, "OUTPUT": "TEMPORARY_OUTPUT"},
            feedback=self.feedback
        )
        return result["OUTPUT"]
    
    def _reproject_layer(self, lyr: QgsVectorLayer, operation: str = "") -> QgsVectorLayer:
        """Reproject layer to target CRS."""
        return processing.run(
            "native:reprojectlayer",
            {
                "INPUT": lyr,
                "TARGET_CRS": self.target_crs,
                "OPERATION": operation,
                "OUTPUT": "TEMPORARY_OUTPUT"
            },
            feedback=self.feedback
        )["OUTPUT"]
    
    def _write_layer(self, vl: QgsVectorLayer, gpkg_path: str, layer_name: str, is_first: bool) -> bool:
        """Write layer to GeoPackage."""
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = layer_name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if is_first
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        ret = QgsVectorFileWriter.writeAsVectorFormatV2(vl, gpkg_path, self.transform_ctx, opts)
        
        if isinstance(ret, tuple):
            code, msg = ret
        else:
            code, msg = ret, ""
        
        if code != QgsVectorFileWriter.NoError:
            self.log(f"❌ Schreibfehler '{layer_name}': Code {code} {('— ' + msg) if msg else ''}")
            return False
        
        status = 'neu' if is_first else 'update'
        self.log(f"✔️  geschrieben: {layer_name} ({status})")
        return True
    
    def _build_wmts_layer(self) -> Optional[QgsRasterLayer]:
        """Build BEV WMTS base layer with XYZ tile fallback."""
        # Try XYZ tile endpoint first (simpler and more reliable with projected CRS)
        # basemap.at provides XYZ tiles for orthofoto
        xyz_url = "https://tiles.geoimage.at/tiles/orthofoto/google/{z}/{x}/{y}.jpg"
        
        ortho = QgsRasterLayer(f"type=xyz&url={xyz_url}", WMTS_LAYER_NAME, "wms")
        if ortho.isValid():
            ortho.setOpacity(1.0)
            self.log("✓ BEV Orthofoto (XYZ Tiles) geladen")
            return ortho
        
        # Fallback: Try WMTS if XYZ fails
        self.log("ℹ️  XYZ-Kacheln nicht verfügbar, versuche WMTS...")
        wmts_params = {
            "contextualWMSLegend": "0",
            "crs": "EPSG:3857",
            "dpiMode": "7",
            "format": "image/jpeg",
            "layers": "bmaporthofoto30cm",
            "styles": "normal",
            "tileMatrixSet": "google3857",
            "url": "https://www.basemap.at/wmts/1.0.0/WMTSCapabilities.xml",
        }
        wmts_uri = "&".join(f"{k}={v}" for k, v in wmts_params.items())
        ortho = QgsRasterLayer(wmts_uri, WMTS_LAYER_NAME, "wms")
        
        if not ortho.isValid():
            self.log("⚠️  BEV Orthofoto konnte nicht geladen werden – Internet erforderlich.")
            return None
        
        ortho.setOpacity(1.0)
        return ortho
    
    def _build_project(self, gpkg_path: str, layer_names: List[str], out_qgz: str):
        """Build and save QGIS project from processed layers."""
        proj = QgsProject.instance()
        proj.clear()
        proj.setFileName(out_qgz)
        proj.setCrs(self.target_crs)  # Set CRS FIRST before adding layers
        root = proj.layerTreeRoot()
        
        # Add WMTS base layer FIRST (bottom of layer stack)
        ortho = self._build_wmts_layer()
        if ortho:
            proj.addMapLayer(ortho)
            # Move to bottom of layer tree
            root.insertLayer(0, proj.removeMapLayer(ortho.id()))
            self.log("✓ BEV Orthofoto-Layer hinzugefügt")
        
        # Load vector layers (on top of base layer)
        for ln in layer_names:
            vl = QgsVectorLayer(f"{gpkg_path}|layername={ln}", ln, "ogr")
            if not vl.isValid():
                self.log(f"⚠️  Layer {ln} konnte nicht geladen werden.")
                continue
            
            # Style polygon layers with transparent fill
            if vl.geometryType() == QgsWkbTypes.PolygonGeometry:
                sym = QgsFillSymbol.createSimple({
                    "color": "0,0,0,0",
                    "outline_color": "0,0,0,255",
                    "outline_width": "0.30",
                    "outline_width_unit": "MM"
                })
                vl.setRenderer(QgsSingleSymbolRenderer(sym))
            
            proj.addMapLayer(vl)
        if proj.write():
            self.log(f"Projektdatei erfolgreich geschrieben: {out_qgz}")
        else:
            self.log("❌ Fehler beim Schreiben der Projektdatei!")
    
    def _apply_geoid_heights(self, gpkg_path: str, geoid_tif: str):
        """Apply geoid height correction to point layers."""
        for ln in self.written_layers:
            vl = QgsVectorLayer(f"{gpkg_path}|layername={ln}", ln, "ogr")
            if not vl.isValid() or vl.geometryType() != QgsWkbTypes.PointGeometry:
                continue
            
            v1 = processing.run(
                "qgis:rastersampling",
                {"INPUT": vl, "RASTERCOPY": geoid_tif, "COLUMN_PREFIX": "N_", "OUTPUT": "TEMPORARY_OUTPUT"},
                feedback=self.feedback
            )["OUTPUT"]
            
            v2 = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": v1,
                    "FIELD_NAME": "H_orth",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "FORMULA": 'z($geometry) - "N_Band1"',
                    "OUTPUT": "TEMPORARY_OUTPUT"
                },
                feedback=self.feedback
            )["OUTPUT"]
            
            self._write_layer(v2, gpkg_path, ln, False)
        
        self.log(f"Orthometrische Höhen berechnet mit {geoid_tif}")
    
    def _write_report(self, ntv2_path: Optional[str], geoid_tif: Optional[str], report_path: str):
        """Write processing report."""
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"BEV→QField Report {datetime.datetime.now().isoformat()}\n")
            f.write(f"SRC_CRS: {self.config.SRC_CRS}\nTGT_CRS: {self.config.TGT_CRS}\n")
            f.write(f"NTV2: {ntv2_path or 'NONE'}\n")
            f.write(f"GEOID: {geoid_tif or 'NONE'}\n")
            f.write("Layers:\n - " + "\n - ".join(self.written_layers) + "\n")
    
    def _setup_qfield_sync(self, basename: str):
        """Create QField sync directory structure."""
        if not self.config.MAKE_SYNC_DIR:
            return
        
        sync_root = self.config.base / "04_QField_Sync"
        sync_dir = sync_root / f"kataster_{basename}_qfield"
        
        try:
            sync_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config.CLEAN_SYNC_DIR:
                for fn in os.listdir(sync_dir):
                    p = sync_dir / fn
                    if p.is_file():
                        try:
                            p.unlink()
                        except Exception:
                            pass
            
            self.log(f"📁 QField Sync Ordner bereit: {sync_dir}")
        except Exception as e:
            self.log(f"⚠️ Konnte QField Sync Ordner nicht anlegen: {e}")
    
    def run(self):
        """Execute main conversion workflow."""
        self.config.ensure_dirs()
        
        # Get input directory
        start_dir = str(self.config.base / "01_BEV_Rohdaten")
        dir_raw = QFileDialog.getExistingDirectory(None, "Ordner mit BEV-Rohdaten auswählen", start_dir)
        if not dir_raw:
            print("❌ Kein Ordner ausgewählt – Abbruch.")
            return
        
        self.log(f"📂 Eingabeordner: {dir_raw}")
        
        basename = os.path.basename(dir_raw.rstrip("/\\"))
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        out_gpkg = self.config.dir_out / f"kataster_{basename}_qfield.gpkg"
        out_qgz = self.config.dir_out / f"kataster_{basename}_qfield.qgz"
        out_rpt = self.config.dir_out / f"kataster_{basename}_qfield_report.txt"
        arch_gpkg = self.config.dir_arch / f"kataster_{basename}_qfield_{stamp}.gpkg"
        arch_qgz = self.config.dir_arch / f"kataster_{basename}_qfield_{stamp}.qgz"
        tmp_gpkg = self.config.run_temp_dir / TEMP_GPKG_NAME
        
        # Collect input layers
        layers = self.collect_layers(dir_raw)
        if not layers:
            self.log("Keine Eingabedaten gefunden.")
            return
        self.log(f"{len(layers)} Eingabe-Layer gefunden.")
        
        # Setup coordinate transformation
        ntv2_path = self._find_ntv2_grid()
        operation = ""
        if ntv2_path:
            # Quote the path in case it contains spaces
            quoted_path = ntv2_path.replace("\\", "/")  # Normalize to forward slashes
            operation = (
                "+proj=pipeline "
                f'+step +proj=hgridshift +grids="{quoted_path}" '
                "+step +proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs"
            )
            self.log(f"NTv2 aktiv: {ntv2_path}")
        else:
            self.log("WARN: Kein *.gsb gefunden – NTv2 wird NICHT erzwungen!")
        
        # Process layers
        first_write = True
        for idx, src in enumerate(layers, 1):
            self.log(f"[{idx}/{len(layers)}] {src.name()}")
            
            inlyr = self._ensure_crs(src)
            inlyr = self._fix_geometries(inlyr)
            reproj = self._reproject_layer(inlyr, operation)
            
            lname = self._safe_name(src.name())
            if self._write_layer(reproj, str(tmp_gpkg), lname, first_write):
                first_write = False
                self.written_layers.append(lname)
        
        if not tmp_gpkg.exists():
            self.log("❌ Abbruchhinweis: kataster_qfield.gpkg existiert nicht – bitte Logs oben prüfen.")
            return
        
        # Move output GPKG
        try:
            if out_gpkg.exists():
                out_gpkg.unlink()
            shutil.move(str(tmp_gpkg), str(out_gpkg))
        except (FileNotFoundError, PermissionError, shutil.Error) as e:
            self.log(f"⚠️ Konnte Datei nicht verschieben: {e}, kopiere stattdessen...")
            shutil.copy2(str(tmp_gpkg), str(out_gpkg))
        
        self.log(f"📦 Output-GPKG bereit: {out_gpkg}")
        
        # Apply geoid heights if available
        geoid_tif = self._find_geoid()
        if geoid_tif and os.path.exists(geoid_tif):
            self._apply_geoid_heights(str(out_gpkg), geoid_tif)
        else:
            self.log("Kein Geoid-Raster gefunden – Höhen bleiben ellipsoidisch.")
        
        # Build QGIS project
        self._build_project(str(out_gpkg), self.written_layers, str(out_qgz))
        
        # Write report
        self._write_report(ntv2_path, geoid_tif, str(out_rpt))
        
        # Archive outputs
        try:
            shutil.copy2(str(out_gpkg), str(arch_gpkg))
            shutil.copy2(str(out_qgz), str(arch_qgz))
        except Exception as e:
            self.log(f"⚠️ Archivieren fehlgeschlagen: {e}")
        
        self.log(f"Fertig: {out_gpkg}")
        self.log(f"Projekt: {out_qgz}")
        self.log(f"Report:  {out_rpt}")
        
        # Setup QField sync directory
        self._setup_qfield_sync(basename)
        
        # Optionally open in QGIS
        if self.config.OPEN_QGIS_ON_FINISH:
            try:
                os.startfile(str(out_qgz))
            except Exception as e:
                self.log(f"ℹ️ Konnte QGIS-Projekt nicht automatisch öffnen: {e}")


# ---------- Entry Point ----------
if __name__ == "__main__":
    try:
        base_path = r"C:\Users\Christian\Meine Ablage (ca19770610@gmail.com)\QGIS"
        config = BEVToQFieldConfig(base_path)
        converter = BEVToQField(config)
        converter.run()
    finally:
        # Only exit QGIS if we created the app ourselves (standalone mode)
        if _qgs_app_is_standalone:
            _qgs_app.exitQgis()
