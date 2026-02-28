# QGIS Plugin Script: Kataster-Konverter (EPSG:31255 → EPSG:4258)
# Importiert automatisch nur *.shp-Dateien mit "gst" oder "sgg" im Namen,
# transformiert sie nach EPSG:4258 und speichert sie in das GPKG des aktuellen Projekts.

import os
import re

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
        # Matches gst/sgg as a separate token (e.g. _gst_, -sgg, gst1), avoids incidental matches like "august".
        return re.search(r"(^|[^a-z0-9])(gst|sgg)([^a-z0-9]|$)", base) is not None

    @staticmethod
    def _memory_geometry_for(layer):
        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        if geometry_type == QgsWkbTypes.PolygonGeometry:
            return "MultiPolygon"
        if geometry_type == QgsWkbTypes.PointGeometry:
            return "Point"
        return None

    def run_kataster_converter(self):
        folder = QFileDialog.getExistingDirectory(None, "Wähle Ordner mit Katasterdaten", self.last_folder)
        if not folder:
            return
        self.last_folder = folder

        project_path = QgsProject.instance().fileName()
        if not project_path:
            QMessageBox.critical(None, "Fehler", "Projekt muss gespeichert sein, um Ziel-GPKG zu bestimmen.")
            return

        target_gpkg = os.path.splitext(project_path)[0] + ".gpkg"
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
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
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

        QgsProject.instance().write()

        summary_lines = [
            f"Importiert: {len(imported_layers)} Layer",
            f"Übersprungen: {len(skipped_layers)}",
            f"Fehlgeschlagen: {len(failed_layers)}",
            "",
            f"Ziel-GPKG: {target_gpkg}",
        ]

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
