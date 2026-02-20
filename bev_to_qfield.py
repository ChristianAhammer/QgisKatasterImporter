# bev_to_qfield.py — QGIS 3.44.x
# BEV (MGI/GK) → ETRS89 / UTM33N (EPSG:25833) + optionale Geoid-Höhen
import os, sys, glob, datetime, shutil, tempfile

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

QgsApplication.setPrefixPath(QGIS_PREFIX, True)
qgs = QgsApplication([], True)
qgs.initQgis()
Processing.initialize()

# ---------- Fixe Pfade ----------
BASE = r"C:\Users\Christian\Meine Ablage (ca19770610@gmail.com)\QGIS"

DIR_PROC   = os.path.join(BASE, "02_QGIS_Processing")
DIR_GRIDS  = os.path.join(DIR_PROC, "grids")
DIR_OUT    = os.path.join(BASE, "03_QField_Output")
DIR_ARCH   = os.path.join(DIR_OUT, "archive")

LOCAL_TEMP_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Temp"), "QGIS_Work")
os.makedirs(LOCAL_TEMP_ROOT, exist_ok=True)
RUN_TEMP_DIR = tempfile.mkdtemp(prefix="bev2qfield_", dir=LOCAL_TEMP_ROOT)

TMP_GPKG = os.path.join(RUN_TEMP_DIR, "kataster_qfield_tmp.gpkg")

# ---------------- Einstellungen ----------------
# Lege den QField-Sync-Ordner automatisch an?
MAKE_SYNC_DIR = True

# Falls der Ordner existiert: vorher leeren? (nur Dateien im Ordner, keine Unterordner)
CLEAN_SYNC_DIR = False

# Nach erfolgreichem Lauf das erzeugte Projekt in QGIS öffnen?
OPEN_QGIS_ON_FINISH = False
# ----------------------------------------------

def ensure_dirs():
    for d in (DIR_GRIDS, DIR_OUT, DIR_ARCH, RUN_TEMP_DIR):
        os.makedirs(d, exist_ok=True)

# CRS / Optionen
SRC_CRS = "EPSG:31255"
TGT_CRS = "EPSG:25833"
FIX_GEOM = True

# ---------- Utilities ----------
def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[bev2qfield {ts}] {msg}", flush=True)

def collect_layers(dir_raw):
    pats = ("*.shp","*.gpkg","*.geojson")
    files = []
    for pat in pats:
        files += glob.glob(os.path.join(dir_raw, "**", pat), recursive=True)
    layers = []
    for p in files:
        vl = QgsVectorLayer(p, os.path.splitext(os.path.basename(p))[0], "ogr")
        if vl.isValid():
            layers.append(vl)
    return layers

def safe_name(name):
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)[:60]

def find_ntv2_grid():
    cands = sorted(glob.glob(os.path.join(DIR_GRIDS, "**", "*.gsb"), recursive=True))
    return cands[0].replace("\\","/") if cands else ""

def find_geoid():
    cands = sorted(glob.glob(os.path.join(DIR_GRIDS, "**", "GV_Hoehengrid*.tif"), recursive=True))
    return cands[0] if cands else ""

def reproject_layer(inlyr, target_crs, operation, fb):
    return processing.run("native:reprojectlayer", {
        "INPUT": inlyr, "TARGET_CRS": target_crs,
        "OPERATION": operation, "OUTPUT": "TEMPORARY_OUTPUT"
    }, feedback=fb)["OUTPUT"]

def write_layer(vl, gpkg_path, layer_name, is_first, transform_ctx):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = layer_name
    opts.actionOnExistingFile = (
        QgsVectorFileWriter.CreateOrOverwriteFile if is_first
        else QgsVectorFileWriter.CreateOrOverwriteLayer
    )
    ret = QgsVectorFileWriter.writeAsVectorFormatV2(vl, gpkg_path, transform_ctx, opts)
    if isinstance(ret, tuple):
        code, msg = ret
    else:
        code, msg = ret, ""
    if code != QgsVectorFileWriter.NoError:
        log(f"❌ Schreibfehler '{layer_name}': Code {code} {('— ' + msg) if msg else ''}")
        return False
    log(f"✔️  geschrieben: {layer_name} ({'neu' if is_first else 'update'})")
    return True

def build_project_from_layers(gpkg_path, layer_names, target_crs, out_qgz):
    proj = QgsProject.instance()
    proj.clear()
    proj.setFileName(out_qgz)

    root = proj.layerTreeRoot()

    # 1) Vektorlayer laden und Polygone transparent stellen
    for ln in layer_names:
        vl = QgsVectorLayer(f"{gpkg_path}|layername={ln}", ln, "ogr")
        if not vl.isValid():
            log(f"⚠️  Layer {ln} konnte nicht geladen werden.")
            continue

        # Polygon-Layer: transparente Füllung, nur Umriss
        if vl.geometryType() == QgsWkbTypes.PolygonGeometry:
            sym = QgsFillSymbol.createSimple({
                "color": "0,0,0,0",           # vollständig transparent
                "outline_color": "0,0,0,255", # schwarze Kontur
                "outline_width": "0.30",
                "outline_width_unit": "MM"
            })
            vl.setRenderer(QgsSingleSymbolRenderer(sym))

        proj.addMapLayer(vl)

    # 2) BEV Orthofoto (basemap.at) als WMTS ganz nach unten
    wmts_uri = (
        "contextualWMSLegend=0"
        "&crs=EPSG:3857"
        "&dpiMode=7"
        "&format=image/jpeg"
        "&layers=bmaporthofoto30cm"
        "&styles=normal"
        "&tileMatrixSet=google3857"
        "&url=https://www.basemap.at/wmts/1.0.0/WMTSCapabilities.xml"
    )
    ortho = QgsRasterLayer(wmts_uri, "BEV Orthofoto (basemap.at)", "wms")
    if ortho.isValid():
        proj.addMapLayer(ortho, False)            # nicht automatisch einhängen
        root.insertLayer(len(root.children()), ortho)  # ganz unten platzieren
    else:
        log("⚠️  BEV Orthofoto (WMTS) konnte nicht geladen werden – prüfe Internet/URL.")

    # 3) Projekt-CRS setzen & speichern
    proj.setCrs(target_crs)
    ok = proj.write()
    if ok:
        log(f"Projektdatei erfolgreich geschrieben: {out_qgz}")
    else:
        log("❌ Fehler beim Schreiben der Projektdatei!")



# ---------- Hauptlogik ----------
def main():
    ensure_dirs()
    fb = QgsProcessingFeedback()
    target_crs = QgsCoordinateReferenceSystem(TGT_CRS)
    transform_ctx = QgsProject.instance().transformContext()

    # Eingabeordner wählen
    start_dir = os.path.join(BASE, "01_BEV_Rohdaten")
    dir_raw = QFileDialog.getExistingDirectory(None, "Ordner mit BEV-Rohdaten auswählen", start_dir)
    if not dir_raw:
        print("❌ Kein Ordner ausgewählt – Abbruch.")
        return
    print(f"📂 Eingabeordner: {dir_raw}", flush=True)

    basename = os.path.basename(dir_raw.rstrip("/\\"))
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    OUT_GPKG = os.path.join(DIR_OUT,  f"kataster_{basename}_qfield.gpkg")
    OUT_QGZ  = os.path.join(DIR_OUT,  f"kataster_{basename}_qfield.qgz")
    OUT_RPT  = os.path.join(DIR_OUT,  f"kataster_{basename}_qfield_report.txt")

    ARCH_GPKG = os.path.join(DIR_ARCH, f"kataster_{basename}_qfield_{stamp}.gpkg")
    ARCH_QGZ  = os.path.join(DIR_ARCH, f"kataster_{basename}_qfield_{stamp}.qgz")

    layers = collect_layers(dir_raw)
    if not layers:
        log("Keine Eingabedaten gefunden.")
        return
    log(f"{len(layers)} Eingabe-Layer gefunden.")

    ntv2_path = find_ntv2_grid()
    operation = ""
    if ntv2_path:
        operation = (
            "+proj=pipeline "
            f"+step +proj=hgridshift +grids={ntv2_path} "
            "+step +proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs"
        )
        log(f"NTv2 aktiv: {ntv2_path}")
    else:
        log("WARN: Kein *.gsb gefunden – NTv2 wird NICHT erzwungen!")

    written = []
    first_write_done = False

    for idx, src in enumerate(layers, 1):
        log(f"[{idx}/{len(layers)}] {src.name()}")
        inlyr = src
        if not inlyr.crs().isValid():
            inlyr.setCrs(QgsCoordinateReferenceSystem(SRC_CRS))
        if FIX_GEOM and QgsWkbTypes.geometryType(inlyr.wkbType()) != QgsWkbTypes.UnknownGeometry:
            inlyr = processing.run("native:fixgeometries",
                {"INPUT": inlyr, "METHOD": 0, "OUTPUT": "TEMPORARY_OUTPUT"}, feedback=fb)["OUTPUT"]
        reproj = reproject_layer(inlyr, target_crs, operation, fb)
        lname = safe_name(src.name())
        if write_layer(reproj, TMP_GPKG, lname, not first_write_done, transform_ctx):
            first_write_done = True
            written.append(lname)

    if not os.path.exists(TMP_GPKG):
        log("❌ Abbruchhinweis: kataster_qfield.gpkg existiert nicht – bitte Logs oben prüfen.")
        return

    try:
        if os.path.exists(OUT_GPKG):
            os.remove(OUT_GPKG)
        shutil.move(TMP_GPKG, OUT_GPKG)
    except Exception:
        shutil.copy2(TMP_GPKG, OUT_GPKG)
    log(f"📦 Output-GPKG bereit: {OUT_GPKG}")

    GEOID_TIF = find_geoid()
    if GEOID_TIF and os.path.exists(GEOID_TIF):
        for ln in written:
            vl = QgsVectorLayer(f"{OUT_GPKG}|layername={ln}", ln, "ogr")
            if not vl.isValid() or vl.geometryType() != QgsWkbTypes.PointGeometry:
                continue
            v1 = processing.run("qgis:rastersampling", {
                "INPUT": vl, "RASTERCOPY": GEOID_TIF,
                "COLUMN_PREFIX": "N_", "OUTPUT": "TEMPORARY_OUTPUT"
            }, feedback=fb)["OUTPUT"]
            v2 = processing.run("native:fieldcalculator", {
                "INPUT": v1, "FIELD_NAME": "H_orth",
                "FIELD_TYPE": 0, "FIELD_LENGTH": 20, "FIELD_PRECISION": 3,
                "FORMULA": "z($geometry) - \"N_Band1\"",
                "OUTPUT": "TEMPORARY_OUTPUT"
            }, feedback=fb)["OUTPUT"]
            write_layer(v2, OUT_GPKG, ln, False, transform_ctx)
        log(f"Orthometrische Höhen berechnet mit {GEOID_TIF}")
    else:
        log("Kein Geoid-Raster gefunden – Höhen bleiben ellipsoidisch.")

    build_project_from_layers(OUT_GPKG, written, target_crs, OUT_QGZ)

    with open(OUT_RPT, "w", encoding="utf-8") as f:
        f.write(f"BEV→QField Report {datetime.datetime.now().isoformat()}\n")
        f.write(f"SRC_CRS: {SRC_CRS}\nTGT_CRS: {TGT_CRS}\n")
        f.write(f"NTV2: {ntv2_path or 'NONE'}\n")
        f.write(f"GEOID: {GEOID_TIF or 'NONE'}\n")
        f.write("Layers:\n - " + "\n - ".join(written) + "\n")

    # ---------- Archiv-Kopie ----------
    try:
        shutil.copy2(OUT_GPKG, ARCH_GPKG)
        shutil.copy2(OUT_QGZ,  ARCH_QGZ)
    except Exception:
        pass

    log(f"Fertig: {OUT_GPKG}")
    log(f"Projekt: {OUT_QGZ}")
    log(f"Report:  {OUT_RPT}")
    
    # --- QField Sync: nur Ordner anlegen / optional leeren ---
    if MAKE_SYNC_DIR:
        SYNC_ROOT = os.path.join(BASE, "04_QField_Sync")
        SYNC_DIR  = os.path.join(SYNC_ROOT, f"kataster_{basename}_qfield")
        try:
            os.makedirs(SYNC_DIR, exist_ok=True)
            if CLEAN_SYNC_DIR:
                for fn in os.listdir(SYNC_DIR):
                    p = os.path.join(SYNC_DIR, fn)
                    if os.path.isfile(p):
                        try: os.remove(p)
                        except Exception: pass
            log(f"📁 QField Sync Ordner bereit: {SYNC_DIR}")
        except Exception as e:
            log(f"⚠️ Konnte QField Sync Ordner nicht anlegen: {e}")

    # --- Optional: Projekt in QGIS öffnen ---
    if OPEN_QGIS_ON_FINISH:
        try:
            os.startfile(OUT_QGZ)  # öffnet das Projekt mit QGIS (Windows)
        except Exception as e:
            log(f"ℹ️ Konnte QGIS-Projekt nicht automatisch öffnen: {e}")

# ---------- Start / Cleanup ----------
if __name__ == "__main__":
    try:
        main()
    finally:
        qgs.exitQgis()
