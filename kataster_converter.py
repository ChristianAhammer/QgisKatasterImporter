# QGIS Plugin Script: Kataster-Konverter (EPSG:31255 → EPSG:25833)
# Importiert automatisch nur *.shp-Dateien mit "gst" oder "sgg" im Namen,
# transformiert sie nach EPSG:25833 und speichert sie in das GPKG des aktuellen Projekts.

import datetime
import glob
import math
import os
import re
import sqlite3
try:
    import processing
except ModuleNotFoundError:
    processing = None

from kataster_common import (
    dedupe_paths,
    default_output_path,
    is_kataster_shapefile,
    qgis_base_from_source,
    qgis_base_from_target,
)

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsProject,
    QgsRasterLayer,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)


class KatasterConverterPlugin:
    ORTHOFOTO_LAYER_NAME = "BEV Orthofoto (basemap.at)"

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.last_folder = "C:/QgisData/entzippt"

    def initGui(self):
        icon = QIcon()
        self.action = QAction(icon, "Kataster-Konverter (31255 → 25833)", self.iface.mainWindow())
        self.action.triggered.connect(self.run_kataster_converter)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Kataster-Konverter", self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Kataster-Konverter", self.action)
            self.iface.removeToolBarIcon(self.action)

    @staticmethod
    def _is_kataster_shapefile(filename):
        return is_kataster_shapefile(filename)

    @staticmethod
    def _memory_geometry_for(layer):
        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        if geometry_type == QgsWkbTypes.PolygonGeometry:
            return "MultiPolygon"
        if geometry_type == QgsWkbTypes.PointGeometry:
            return "Point"
        return None

    @staticmethod
    def _is_kataster_project_layer_name(layer_name):
        lower = (layer_name or "").lower()
        return re.search(r"(?<![a-z])(fpt|gnr|gst|nfl|nsl|nsy|sgg|ssb|vgg)(?![a-z])", lower) is not None

    def _remove_existing_kataster_layers_from_project(self):
        project = QgsProject.instance()
        remove_ids = []
        for layer_id, layer in project.mapLayers().items():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if not self._is_kataster_project_layer_name(layer.name()):
                continue
            remove_ids.append(layer_id)

        if remove_ids:
            project.removeMapLayers(remove_ids)

    @staticmethod
    def _default_unsaved_output_path(source_folder):
        return default_output_path(source_folder)

    @staticmethod
    def _dedupe_paths(values):
        return dedupe_paths(values)

    @staticmethod
    def _qgis_base_from_source(source_folder):
        return qgis_base_from_source(source_folder)

    @staticmethod
    def _qgis_base_from_target(target_gpkg):
        return qgis_base_from_target(target_gpkg)

    @staticmethod
    def _detail_value(obj, attr, default=None):
        if not hasattr(obj, attr):
            return default
        value = getattr(obj, attr)
        try:
            return value() if callable(value) else value
        except Exception:
            return default

    @staticmethod
    def _select_gisgrid_operation(crs_source, crs_target):
        transform = QgsCoordinateTransform(crs_source, crs_target, QgsCoordinateTransformContext())
        if not hasattr(transform, "instantiatedCoordinateOperationDetails"):
            return None, None, None, [], "QGIS API liefert keine OperationDetails für die Transformationsprüfung."

        details = transform.instantiatedCoordinateOperationDetails()
        operation = KatasterConverterPlugin._detail_value(details, "proj", "") or ""
        operation_name = KatasterConverterPlugin._detail_value(details, "name", "") or ""
        operation_accuracy = KatasterConverterPlugin._detail_value(details, "accuracy", None)
        is_available = bool(KatasterConverterPlugin._detail_value(details, "isAvailable", False))
        grids = KatasterConverterPlugin._detail_value(details, "grids", []) or []

        available_grids = []
        for grid in grids:
            grid_available = bool(KatasterConverterPlugin._detail_value(grid, "isAvailable", True))
            grid_path = (
                KatasterConverterPlugin._detail_value(grid, "fullName", "")
                or KatasterConverterPlugin._detail_value(grid, "shortName", "")
            )
            if grid_available and grid_path:
                available_grids.append(grid_path)

        if not is_available:
            return None, None, None, available_grids, "QGIS meldet die bevorzugte GIS-Grid Transformation als nicht verfügbar."
        if "hgridshift" not in operation.lower():
            return None, None, None, available_grids, "Die aktive Transformation nutzt kein hgridshift/GIS-Grid."
        if not available_grids:
            return None, None, None, available_grids, "Kein verfügbares GIS-Grid in der aktiven Transformation gefunden."

        return operation, operation_name, operation_accuracy, available_grids, None

    @staticmethod
    def _find_ntv2_grid(source_folder, target_gpkg, project_path):
        direct_candidates = []
        for env_key in ("QGIS_GISGRID_GSB", "GISGRID_GSB", "NTV2_GRID_PATH"):
            direct_candidates.append(os.environ.get(env_key))

        for candidate in KatasterConverterPlugin._dedupe_paths(direct_candidates):
            if os.path.isfile(candidate) and candidate.lower().endswith(".gsb"):
                return candidate, [candidate]

        search_dirs = []
        processing_root = os.environ.get("QFC_PROCESSING_ROOT")
        if processing_root:
            search_dirs.append(os.path.join(processing_root, "grids"))

        qgis_base_from_source = KatasterConverterPlugin._qgis_base_from_source(source_folder)
        if qgis_base_from_source:
            search_dirs.append(os.path.join(qgis_base_from_source, "02_QGIS_Processing", "grids"))

        qgis_base_from_target = KatasterConverterPlugin._qgis_base_from_target(target_gpkg)
        if qgis_base_from_target:
            search_dirs.append(os.path.join(qgis_base_from_target, "02_QGIS_Processing", "grids"))

        if project_path:
            project_dir = os.path.dirname(project_path)
            project_base = os.path.normpath(os.path.join(project_dir, ".."))
            search_dirs.append(os.path.join(project_base, "02_QGIS_Processing", "grids"))

        searched = KatasterConverterPlugin._dedupe_paths(search_dirs)
        for search_dir in searched:
            if not os.path.isdir(search_dir):
                continue
            matches = sorted(glob.glob(os.path.join(search_dir, "**", "*.gsb"), recursive=True))
            if matches:
                return os.path.normpath(matches[0]), searched

        return None, searched

    @staticmethod
    def _build_orthofoto_layer():
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
        wmts_uri = "&".join(f"{key}={value}" for key, value in wmts_params.items())

        ortho = QgsRasterLayer(wmts_uri, KatasterConverterPlugin.ORTHOFOTO_LAYER_NAME, "wms")
        if not ortho.isValid():
            return None

        ortho.setOpacity(1.0)
        return ortho

    @staticmethod
    def _move_layer_to_bottom(project, layer_id):
        root = project.layerTreeRoot()
        node = root.findLayer(layer_id)
        if not node:
            return

        parent = node.parent() or root
        clone = node.clone()
        parent.removeChildNode(node)
        parent.addChildNode(clone)

    @staticmethod
    def _ensure_orthofoto_layer(project):
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.name() == KatasterConverterPlugin.ORTHOFOTO_LAYER_NAME:
                KatasterConverterPlugin._move_layer_to_bottom(project, layer.id())
                return

        ortho = KatasterConverterPlugin._build_orthofoto_layer()
        if ortho and ortho.isValid():
            project.addMapLayer(ortho)
            KatasterConverterPlugin._move_layer_to_bottom(project, ortho.id())

    @staticmethod
    def _write_output_project(gpkg_path, layer_names, target_crs):
        output_qgz = os.path.splitext(gpkg_path)[0] + ".qgz"
        output_project = QgsProject()
        output_project.setFileName(output_qgz)
        output_project.setCrs(target_crs)
        KatasterConverterPlugin._ensure_orthofoto_layer(output_project)

        for layer_name in layer_names:
            layer = QgsVectorLayer(f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
            if not layer.isValid():
                return None, f"Layer konnte nicht aus GPKG geladen werden: {layer_name}"

            if "gst" in layer_name.lower() and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
                if symbol and hasattr(symbol.symbolLayer(0), "setBrushStyle"):
                    symbol.symbolLayer(0).setBrushStyle(0)  # Qt.NoBrush
                layer.setRenderer(QgsSingleSymbolRenderer(symbol))

            output_project.addMapLayer(layer)

        KatasterConverterPlugin._ensure_orthofoto_layer(output_project)

        if not output_project.write():
            return None, "QGIS-Projektdatei konnte nicht geschrieben werden"

        return output_qgz, None

    @staticmethod
    def _list_gpkg_layers(gpkg_path):
        if not os.path.exists(gpkg_path):
            return [], f"GPKG nicht gefunden: {gpkg_path}"

        try:
            with sqlite3.connect(gpkg_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT table_name
                    FROM gpkg_contents
                    WHERE data_type = 'features'
                    ORDER BY table_name
                    """
                )
                rows = cursor.fetchall()
            return [row[0] for row in rows], None
        except sqlite3.Error as err:
            return [], f"GPKG-Layerliste konnte nicht gelesen werden: {err}"

    @staticmethod
    def _write_report(report_path, source_folder, target_gpkg, output_qgz, ntv2_grid, imported_layers, skipped_layers, failed_layers):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Kataster-Konverter Report: {timestamp}",
            f"Quelle: {source_folder}",
            f"Ziel-GPKG: {target_gpkg}",
            f"Ziel-QGZ: {output_qgz or 'nicht erstellt'}",
            f"GIS-Grid: {ntv2_grid or 'nicht gefunden'}",
            "",
            f"Importiert ({len(imported_layers)}):",
        ]
        lines.extend([f"- {name}" for name in imported_layers] or ["- keine"])

        lines.append("")
        lines.append(f"Übersprungen ({len(skipped_layers)}):")
        lines.extend([f"- {item}" for item in skipped_layers] or ["- keine"])

        lines.append("")
        lines.append(f"Fehlgeschlagen ({len(failed_layers)}):")
        lines.extend([f"- {item}" for item in failed_layers] or ["- keine"])

        try:
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            return None
        except OSError as err:
            return str(err)

    def run_kataster_converter(self):
        if processing is None:
            QMessageBox.critical(
                None,
                "Processing fehlt",
                "QGIS Processing-Modul konnte nicht geladen werden. "
                "Bitte Processing-Plugin aktivieren und erneut starten.",
            )
            return

        folder = QFileDialog.getExistingDirectory(None, "Wähle Ordner mit Katasterdaten", self.last_folder)
        if not folder:
            return
        self.last_folder = folder

        project_path = QgsProject.instance().fileName()
        project_is_saved = bool(project_path)

        if project_is_saved:
            target_gpkg = os.path.splitext(project_path)[0] + ".gpkg"
        else:
            default_gpkg = self._default_unsaved_output_path(folder)
            default_gpkg_dir = os.path.dirname(default_gpkg)
            try:
                os.makedirs(default_gpkg_dir, exist_ok=True)
            except OSError:
                pass

            target_gpkg, _ = QFileDialog.getSaveFileName(
                None,
                "Ziel-GPKG wählen",
                default_gpkg,
                "GeoPackage (*.gpkg)",
            )
            if not target_gpkg:
                return
            if not target_gpkg.lower().endswith(".gpkg"):
                target_gpkg += ".gpkg"

        gpkg_folder = os.path.dirname(target_gpkg)
        if not os.access(gpkg_folder, os.W_OK):
            QMessageBox.critical(None, "Zugriffsfehler", f"Kein Schreibzugriff auf Verzeichnis: {gpkg_folder}")
            return

        print(f"Ziel-GPKG: {target_gpkg}")

        crs_source = QgsCoordinateReferenceSystem("EPSG:31255")
        crs_target = QgsCoordinateReferenceSystem("EPSG:25833")
        ntv2_grid, searched_grid_dirs = self._find_ntv2_grid(folder, target_gpkg, project_path)
        if not ntv2_grid:
            searched_info = "\n".join(f"- {path}" for path in searched_grid_dirs) if searched_grid_dirs else "- keine Suchpfade ableitbar"
            QMessageBox.critical(
                None,
                "GIS-Grid fehlt",
                "Kein GIS_Grid (*.gsb) gefunden.\n"
                "Die Transformation wird aus Genauigkeitsgründen abgebrochen.\n\n"
                "Gesucht in:\n"
                f"{searched_info}",
            )
            return

        operation, operation_name, operation_accuracy, operation_grids, operation_error = self._select_gisgrid_operation(
            crs_source, crs_target
        )
        if operation_error:
            QMessageBox.critical(
                None,
                "Transformationsfehler",
                f"{operation_error}\nAusgewählte lokale GIS-Grid Datei: {ntv2_grid}",
            )
            return
        transform_context = QgsCoordinateTransformContext()

        imported_layers = []
        skipped_layers = []
        failed_layers = []

        # Avoid old converted layers masking the current GST/SGG output.
        self._remove_existing_kataster_layers_from_project()
        self._ensure_orthofoto_layer(QgsProject.instance())
        gpkg_exists = os.path.exists(target_gpkg)

        for filename in sorted(os.listdir(folder)):
            if not self._is_kataster_shapefile(filename):
                continue

            lower_filename = filename.lower()
            full_path = os.path.join(folder, filename)
            layer = QgsVectorLayer(full_path, filename, "ogr")
            if not layer.isValid():
                failed_layers.append(f"{filename}: Layer konnte nicht geladen werden")
                continue

            if not layer.crs().isValid() or layer.crs().authid() == "":
                layer.setCrs(crs_source)

            layer_name = os.path.splitext(filename)[0]
            uri = f"{target_gpkg}|layername={layer_name}"

            geometry = self._memory_geometry_for(layer)
            if geometry is None:
                skipped_layers.append(f"{filename}: nicht unterstützter Geometrietyp")
                continue

            try:
                reprojected = processing.run(
                    "native:reprojectlayer",
                    {
                        "INPUT": layer,
                        "TARGET_CRS": crs_target,
                        "OPERATION": operation,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )["OUTPUT"]
            except Exception as err:
                failed_layers.append(f"{filename}: Reprojektion fehlgeschlagen ({err})")
                continue

            extent = reprojected.extent()
            extent_values = [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()]
            if not all(math.isfinite(value) for value in extent_values):
                failed_layers.append(f"{filename}: Reprojektion lieferte ungültige Ausdehnung {extent_values}")
                continue

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name
            options.fileEncoding = "UTF-8"
            if gpkg_exists:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

            err, msg = QgsVectorFileWriter.writeAsVectorFormatV2(
                reprojected,
                target_gpkg,
                transform_context,
                options,
            )

            if err != QgsVectorFileWriter.NoError:
                failed_layers.append(f"{filename}: Exportfehler ({msg})")
                continue

            gpkg_exists = True

            loaded_layer = QgsVectorLayer(uri, layer_name, "ogr")
            if not loaded_layer.isValid():
                failed_layers.append(f"{filename}: Konnte nach Export nicht aus GPKG geladen werden")
                continue

            if "gst" in lower_filename and QgsWkbTypes.geometryType(loaded_layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
                if symbol and hasattr(symbol.symbolLayer(0), "setBrushStyle"):
                    symbol.symbolLayer(0).setBrushStyle(0)  # Qt.NoBrush
                renderer = QgsSingleSymbolRenderer(symbol)
                loaded_layer.setRenderer(renderer)

            QgsProject.instance().addMapLayer(loaded_layer)
            imported_layers.append(layer_name)

        try:
            os.utime(target_gpkg, None)
        except OSError as err:
            failed_layers.append(f"Zeitstempel konnte nicht aktualisiert werden: {err}")

        output_qgz = None
        desired_output_qgz = os.path.splitext(target_gpkg)[0] + ".qgz"
        active_project = QgsProject.instance()

        # For initially unsaved sessions, always bind the active project
        # to the output folder project path (not any temporary QGIS path).
        if not project_is_saved:
            active_project.setFileName(desired_output_qgz)

        if active_project.fileName():
            output_qgz = active_project.fileName()
            if not active_project.write():
                failed_layers.append("Projektdatei: Aktuelles QGIS-Projekt konnte nicht geschrieben werden")
                output_qgz = None

        if not output_qgz:
            qgz_layers = list(imported_layers)
            if not qgz_layers:
                qgz_layers, list_error = self._list_gpkg_layers(target_gpkg)
                if list_error:
                    failed_layers.append(f"Projektdatei: {list_error}")

            if qgz_layers:
                output_qgz, project_error = self._write_output_project(target_gpkg, qgz_layers, crs_target)
                if project_error:
                    failed_layers.append(f"Projektdatei: {project_error}")

        report_path = os.path.splitext(target_gpkg)[0] + "_report.txt"
        report_error = self._write_report(
            report_path,
            folder,
            target_gpkg,
            output_qgz,
            ntv2_grid,
            imported_layers,
            skipped_layers,
            failed_layers,
        )
        if report_error:
            failed_layers.append(f"Reportdatei: {report_error}")
            report_path = None

        summary_lines = [
            f"Importiert: {len(imported_layers)} Layer",
            f"Übersprungen: {len(skipped_layers)}",
            f"Fehlgeschlagen: {len(failed_layers)}",
            "",
            f"Ziel-GPKG: {target_gpkg}",
            f"GIS-Grid: {ntv2_grid}",
        ]
        if operation_name:
            summary_lines.append(f"Transform: {operation_name}")
        if operation_grids:
            summary_lines.append(f"Aktives Grid: {operation_grids[0]}")
        if operation_accuracy is not None:
            summary_lines.append(f"Transform-Genauigkeit: {operation_accuracy} m")

        if output_qgz:
            summary_lines.append(f"Ziel-QGZ: {output_qgz}")
        if report_path:
            summary_lines.append(f"Report: {report_path}")
        if skipped_layers:
            summary_lines.append("")
            summary_lines.append("Übersprungene Dateien:")
            summary_lines.extend(skipped_layers[:10])
            if len(skipped_layers) > 10:
                summary_lines.append(f"... und {len(skipped_layers) - 10} weitere")

        if failed_layers:
            summary_lines.append("")
            summary_lines.append("Fehler:")
            summary_lines.extend(failed_layers[:10])
            if len(failed_layers) > 10:
                summary_lines.append(f"... und {len(failed_layers) - 10} weitere")

        summary_lines.append("")
        summary_lines.append("Hinweis: Falls du QFieldCloud nutzt, bitte manuell synchronisieren!")

        QMessageBox.information(None, "Kataster-Konverter", "\n".join(summary_lines))
