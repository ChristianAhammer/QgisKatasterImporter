# QGIS Plugin Script: Kataster-Konverter (EPSG:31255 → EPSG:4258)
# Importiert automatisch nur *.shp-Dateien mit "gst" oder "sgg" im Namen,
# transformiert sie nach EPSG:4258 und speichert sie in das GPKG des aktuellen Projekts.

from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCoordinateTransform,
    QgsWkbTypes,
    QgsSymbol,
    QgsSingleSymbolRenderer,
    QgsFeature,
    QgsVectorDataProvider
)
import os
import time

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

        for filename in os.listdir(folder):
            if not filename.lower().endswith('.shp'):
                continue
            if 'gst' not in filename.lower() and 'sgg' not in filename.lower():
                continue

            full_path = os.path.join(folder, filename)
            layer = QgsVectorLayer(full_path, filename, "ogr")
            if not layer.isValid():
                QMessageBox.warning(None, "Layer ungültig", f"Layer konnte nicht geladen werden: {filename}")
                continue

            if not layer.crs().isValid() or layer.crs().authid() == '':
                layer.setCrs(crs_source)

            print(f"Lade: {filename} → gültig: {layer.isValid()} → {layer.crs().authid()}")

            layer_name = os.path.splitext(filename)[0]
            uri = f"{target_gpkg}|layername={layer_name}"

            # Reprojektion
            geometry_type = QgsWkbTypes.displayString(layer.wkbType()).lower()
            geometry = "MultiPolygon" if "polygon" in geometry_type else "Point"
            reprojected = QgsVectorLayer(f"{geometry}?crs=EPSG:4258", layer_name, "memory")
            reprojected_data: QgsVectorDataProvider = reprojected.dataProvider()
            reprojected_data.addAttributes(layer.fields())
            reprojected.updateFields()

            for feat in layer.getFeatures():
                new_feat = QgsFeature()
                new_feat.setFields(reprojected.fields())
                new_feat.setAttributes(feat.attributes())
                geom = feat.geometry()
                geom.transform(coordinate_transform)
                new_feat.setGeometry(geom)
                reprojected_data.addFeature(new_feat)

            reprojected.updateExtents()

            # Export ins GPKG
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
                options
            )

            if err != QgsVectorFileWriter.NoError:
                print(f"Fehler beim Exportieren von {layer_name}: {msg}")
                QMessageBox.warning(None, "Exportfehler", f"Fehler beim Exportieren von {layer_name}: {msg}")
                continue

            loaded_layer = QgsVectorLayer(uri, layer_name, "ogr")
            if not loaded_layer.isValid():
                print(f"Fehler beim Laden von {layer_name} aus GPKG")
                continue

            if 'gst' in filename.lower() and QgsWkbTypes.geometryType(loaded_layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
                if symbol and hasattr(symbol.symbolLayer(0), 'setBrushStyle'):
                    symbol.symbolLayer(0).setBrushStyle(0)  # Qt.NoBrush
                renderer = QgsSingleSymbolRenderer(symbol)
                loaded_layer.setRenderer(renderer)

            QgsProject.instance().addMapLayer(loaded_layer)
            imported_layers.append(layer_name)

        # Zeitstempel des GPKG anpassen (damit QFieldCloud erkennt: geändert)
        try:
            os.utime(target_gpkg, None)
        except Exception as e:
            print(f"Fehler beim Aktualisieren des GPKG-Zeitstempels: {e}")

        # Projekt speichern
        QgsProject.instance().write()

        QMessageBox.information(
            None,
            "Fertig",
            f"Alle passenden Kataster-Layer wurden (nach EPSG:4258) in das Projekt-GPKG exportiert und geladen:\n\n{target_gpkg}\n\n⚠ Hinweis: Falls du QFieldCloud nutzt, bitte manuell synchronisieren!"
        )
