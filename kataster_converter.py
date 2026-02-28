# QGIS Plugin Script: Kataster-Konverter (EPSG:31255 → EPSG:4258)
# Importiert automatisch nur *.shp-Dateien mit "gst" oder "sgg" im Namen,
# transformiert sie nach EPSG:4258 und speichert sie in das GPKG des aktuellen Projekts.

import datetime
import os
import re
import shutil
import sqlite3

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsVectorDataProvider,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)


class KatasterConverterPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.last_folder = "C:/QgisData/entzippt"

    def initGui(self):
        icon = QIcon()
        self.action = QAction(icon, "Kataster-Konverter (31255 → 4258)", self.iface.mainWindow())
        self.action.triggered.connect(self.run_kataster_converter)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Kataster-Konverter", self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Kataster-Konverter", self.action)
            self.iface.removeToolBarIcon(self.action)

    @staticmethod
    def _is_kataster_shapefile(filename):
        lower = filename.lower()
        if not lower.endswith(".shp"):
            return False

        base = os.path.splitext(lower)[0]
        # Match GST/SGG only when not embedded in a larger word,
        # while still allowing cadastral names like 44106GST_V2.
        return re.search(r"(?<![a-z])(gst|sgg)(?![a-z])", base) is not None

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
        folder_norm = os.path.normpath(source_folder)
        folder_name = re.split(r"[\\/]+", folder_norm.rstrip("\\/"))[-1] or "kataster_output"

        # Keep compatibility with old BEV workflow: 01_BEV_Rohdaten/<name> -> 03_QField_Output/kataster_<name>_qfield.gpkg
        match = re.search(r"^(.*?)[\\/]01_bev_rohdaten(?:[\\/].*)?$", folder_norm, flags=re.IGNORECASE)
        if match:
            output_root = os.path.join(match.group(1), "03_QField_Output")
        else:
            output_root = folder_norm

        return os.path.join(output_root, f"kataster_{folder_name}_qfield.gpkg")

    @staticmethod
    def _write_output_project(gpkg_path, layer_names, target_crs):
        output_qgz = os.path.splitext(gpkg_path)[0] + ".qgz"
        output_project = QgsProject()
        output_project.setFileName(output_qgz)
        output_project.setCrs(target_crs)

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
    def _write_report(report_path, source_folder, target_gpkg, output_qgz, imported_layers, skipped_layers, failed_layers):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Kataster-Konverter Report: {timestamp}",
            f"Quelle: {source_folder}",
            f"Ziel-GPKG: {target_gpkg}",
            f"Ziel-QGZ: {output_qgz or 'nicht erstellt'}",
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

    @staticmethod
    def _archive_outputs(target_gpkg, output_qgz, report_path):
        output_dir = os.path.dirname(target_gpkg)
        if os.path.basename(output_dir).lower() != "03_qfield_output":
            return [], None

        archive_dir = os.path.join(output_dir, "archive")
        try:
            os.makedirs(archive_dir, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            base = os.path.splitext(os.path.basename(target_gpkg))[0]

            archived = []
            for src in [target_gpkg, output_qgz, report_path]:
                if not src or not os.path.exists(src):
                    continue
                ext = os.path.splitext(src)[1]
                dst = os.path.join(archive_dir, f"{base}_{stamp}{ext}")
                shutil.copy2(src, dst)
                archived.append(dst)

            return archived, None
        except OSError as err:
            return [], str(err)

    def run_kataster_converter(self):
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
        crs_target = QgsCoordinateReferenceSystem("EPSG:4258")
        transform_context: QgsCoordinateTransformContext = QgsProject.instance().transformContext()
        coordinate_transform = QgsCoordinateTransform(crs_source, crs_target, transform_context)

        imported_layers = []
        skipped_layers = []
        failed_layers = []

        # Avoid old converted layers masking the current GST/SGG output.
        self._remove_existing_kataster_layers_from_project()
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

            reprojected = QgsVectorLayer(f"{geometry}?crs=EPSG:4258", layer_name, "memory")
            reprojected_data: QgsVectorDataProvider = reprojected.dataProvider()
            reprojected_data.addAttributes(layer.fields())
            reprojected.updateFields()

            feature_error = None
            for feat in layer.getFeatures():
                new_feat = QgsFeature()
                new_feat.setFields(reprojected.fields())
                new_feat.setAttributes(feat.attributes())
                geom = feat.geometry()

                transform_status = geom.transform(coordinate_transform)
                if transform_status != 0:
                    feature_error = f"Geometrie-Transform fehlgeschlagen (Code {transform_status})"
                    break
                new_feat.setGeometry(geom)
                if not reprojected_data.addFeature(new_feat):
                    feature_error = "Feature konnte nicht in den Reprojektions-Layer geschrieben werden"
                    break

            if feature_error:
                failed_layers.append(f"{filename}: {feature_error}")
                continue

            reprojected.updateExtents()

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name
            options.fileEncoding = "UTF-8"
            if gpkg_exists:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            options.destinationCrs = crs_target

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
            imported_layers,
            skipped_layers,
            failed_layers,
        )
        if report_error:
            failed_layers.append(f"Reportdatei: {report_error}")
            report_path = None

        archived_files, archive_error = self._archive_outputs(target_gpkg, output_qgz, report_path)
        if archive_error:
            failed_layers.append(f"Archivierung: {archive_error}")

        summary_lines = [
            f"Importiert: {len(imported_layers)} Layer",
            f"Übersprungen: {len(skipped_layers)}",
            f"Fehlgeschlagen: {len(failed_layers)}",
            "",
            f"Ziel-GPKG: {target_gpkg}",
        ]

        if output_qgz:
            summary_lines.append(f"Ziel-QGZ: {output_qgz}")
        if report_path:
            summary_lines.append(f"Report: {report_path}")
        if archived_files:
            summary_lines.append(f"Archiv: {os.path.dirname(archived_files[0])} ({len(archived_files)} Datei(en))")

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
