#!/usr/bin/env python3
"""Headless Kataster converter using PyQGIS.

Run via QGIS Python environment (e.g. python-qgis-ltr.bat):
    python kataster_converter_cli.py --source <folder> [--target <path.gpkg>]
"""

import argparse
import datetime
import os
import re
import shutil
import sqlite3
import sys

from qgis.core import (
    QgsApplication,
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


def is_kataster_shapefile(filename):
    lower = filename.lower()
    if not lower.endswith('.shp'):
        return False
    base = os.path.splitext(lower)[0]
    return re.search(r'(?<![a-z])(gst|sgg)(?![a-z])', base) is not None


def memory_geometry_for(layer):
    geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
    if geometry_type == QgsWkbTypes.PolygonGeometry:
        return 'MultiPolygon'
    if geometry_type == QgsWkbTypes.PointGeometry:
        return 'Point'
    return None


def default_output_path(source_folder):
    folder_norm = os.path.normpath(source_folder)
    folder_name = re.split(r'[\\/]+', folder_norm.rstrip('\\/'))[-1] or 'kataster_output'

    match = re.search(r'^(.*?)[\\/]01_bev_rohdaten(?:[\\/].*)?$', folder_norm, flags=re.IGNORECASE)
    if match:
        output_root = os.path.join(match.group(1), '03_QField_Output')
    else:
        output_root = folder_norm

    return os.path.join(output_root, f'kataster_{folder_name}_qfield.gpkg')


def list_gpkg_layers(gpkg_path):
    if not os.path.exists(gpkg_path):
        return [], f'GPKG nicht gefunden: {gpkg_path}'

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
        return [], f'GPKG-Layerliste konnte nicht gelesen werden: {err}'


def write_output_project(gpkg_path, layer_names, target_crs):
    output_qgz = os.path.splitext(gpkg_path)[0] + '.qgz'
    output_project = QgsProject()
    output_project.setFileName(output_qgz)
    output_project.setCrs(target_crs)

    for layer_name in layer_names:
        layer = QgsVectorLayer(f'{gpkg_path}|layername={layer_name}', layer_name, 'ogr')
        if not layer.isValid():
            return None, f'Layer konnte nicht aus GPKG geladen werden: {layer_name}'

        if 'gst' in layer_name.lower() and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
            symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
            if symbol and hasattr(symbol.symbolLayer(0), 'setBrushStyle'):
                symbol.symbolLayer(0).setBrushStyle(0)  # Qt.NoBrush
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        output_project.addMapLayer(layer)

    if not output_project.write():
        return None, 'QGIS-Projektdatei konnte nicht geschrieben werden'

    return output_qgz, None


def write_report(report_path, source_folder, target_gpkg, output_qgz, imported_layers, skipped_layers, failed_layers):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        f'Kataster-Konverter Report: {timestamp}',
        f'Quelle: {source_folder}',
        f'Ziel-GPKG: {target_gpkg}',
        f'Ziel-QGZ: {output_qgz or "nicht erstellt"}',
        '',
        f'Importiert ({len(imported_layers)}):',
    ]
    lines.extend([f'- {name}' for name in imported_layers] or ['- keine'])

    lines.append('')
    lines.append(f'Uebersprungen ({len(skipped_layers)}):')
    lines.extend([f'- {item}' for item in skipped_layers] or ['- keine'])

    lines.append('')
    lines.append(f'Fehlgeschlagen ({len(failed_layers)}):')
    lines.extend([f'- {item}' for item in failed_layers] or ['- keine'])

    with open(report_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


def archive_outputs(target_gpkg, output_qgz, report_path):
    output_dir = os.path.dirname(target_gpkg)
    if os.path.basename(output_dir).lower() != '03_qfield_output':
        return [], None

    archive_dir = os.path.join(output_dir, 'archive')
    try:
        os.makedirs(archive_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        base = os.path.splitext(os.path.basename(target_gpkg))[0]

        archived = []
        for src in [target_gpkg, output_qgz, report_path]:
            if not src or not os.path.exists(src):
                continue
            ext = os.path.splitext(src)[1]
            dst = os.path.join(archive_dir, f'{base}_{stamp}{ext}')
            shutil.copy2(src, dst)
            archived.append(dst)

        return archived, None
    except OSError as err:
        return [], str(err)


def convert(source_folder, target_gpkg):
    if not os.path.isdir(source_folder):
        raise RuntimeError(f'Quellordner nicht gefunden: {source_folder}')

    target_gpkg = os.path.normpath(target_gpkg)
    if not target_gpkg.lower().endswith('.gpkg'):
        target_gpkg += '.gpkg'

    gpkg_folder = os.path.dirname(target_gpkg)
    os.makedirs(gpkg_folder, exist_ok=True)

    if not os.access(gpkg_folder, os.W_OK):
        raise RuntimeError(f'Kein Schreibzugriff auf Verzeichnis: {gpkg_folder}')

    crs_source = QgsCoordinateReferenceSystem('EPSG:31255')
    crs_target = QgsCoordinateReferenceSystem('EPSG:4258')
    transform_context = QgsCoordinateTransformContext()
    coordinate_transform = QgsCoordinateTransform(crs_source, crs_target, transform_context)

    imported_layers = []
    skipped_layers = []
    failed_layers = []

    for filename in sorted(os.listdir(source_folder)):
        if not is_kataster_shapefile(filename):
            continue

        lower_filename = filename.lower()
        full_path = os.path.join(source_folder, filename)
        layer = QgsVectorLayer(full_path, filename, 'ogr')
        if not layer.isValid():
            failed_layers.append(f'{filename}: Layer konnte nicht geladen werden')
            continue

        if not layer.crs().isValid() or layer.crs().authid() == '':
            layer.setCrs(crs_source)

        layer_name = os.path.splitext(filename)[0]
        geometry = memory_geometry_for(layer)
        if geometry is None:
            skipped_layers.append(f'{filename}: nicht unterstuetzter Geometrietyp')
            continue

        reprojected = QgsVectorLayer(f'{geometry}?crs=EPSG:4258', layer_name, 'memory')
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
                feature_error = f'Geometrie-Transform fehlgeschlagen (Code {transform_status})'
                break
            new_feat.setGeometry(geom)
            if not reprojected_data.addFeature(new_feat):
                feature_error = 'Feature konnte nicht in den Reprojektions-Layer geschrieben werden'
                break

        if feature_error:
            failed_layers.append(f'{filename}: {feature_error}')
            continue

        reprojected.updateExtents()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.layerName = layer_name
        options.fileEncoding = 'UTF-8'
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        options.destinationCrs = crs_target

        err, msg = QgsVectorFileWriter.writeAsVectorFormatV2(
            reprojected,
            target_gpkg,
            transform_context,
            options,
        )

        if err != QgsVectorFileWriter.NoError:
            failed_layers.append(f'{filename}: Exportfehler ({msg})')
            continue

        loaded_layer = QgsVectorLayer(f'{target_gpkg}|layername={layer_name}', layer_name, 'ogr')
        if not loaded_layer.isValid():
            failed_layers.append(f'{filename}: Konnte nach Export nicht aus GPKG geladen werden')
            continue

        if 'gst' in lower_filename and QgsWkbTypes.geometryType(loaded_layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
            symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
            if symbol and hasattr(symbol.symbolLayer(0), 'setBrushStyle'):
                symbol.symbolLayer(0).setBrushStyle(0)
            loaded_layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        imported_layers.append(layer_name)

    try:
        os.utime(target_gpkg, None)
    except OSError as err:
        failed_layers.append(f'Zeitstempel konnte nicht aktualisiert werden: {err}')

    qgz_layers = list(imported_layers)
    if not qgz_layers:
        qgz_layers, list_error = list_gpkg_layers(target_gpkg)
        if list_error:
            failed_layers.append(f'Projektdatei: {list_error}')

    output_qgz = None
    if qgz_layers:
        output_qgz, project_error = write_output_project(target_gpkg, qgz_layers, crs_target)
        if project_error:
            failed_layers.append(f'Projektdatei: {project_error}')

    report_path = os.path.splitext(target_gpkg)[0] + '_report.txt'
    try:
        write_report(
            report_path,
            source_folder,
            target_gpkg,
            output_qgz,
            imported_layers,
            skipped_layers,
            failed_layers,
        )
    except OSError as err:
        failed_layers.append(f'Reportdatei: {err}')
        report_path = None

    archived_files, archive_error = archive_outputs(target_gpkg, output_qgz, report_path)
    if archive_error:
        failed_layers.append(f'Archivierung: {archive_error}')

    return {
        'target_gpkg': target_gpkg,
        'output_qgz': output_qgz,
        'report_path': report_path,
        'imported_layers': imported_layers,
        'skipped_layers': skipped_layers,
        'failed_layers': failed_layers,
        'archived_files': archived_files,
    }


def print_summary(result):
    print(f"Importiert: {len(result['imported_layers'])} Layer")
    print(f"Uebersprungen: {len(result['skipped_layers'])}")
    print(f"Fehlgeschlagen: {len(result['failed_layers'])}")
    print('')
    print(f"Ziel-GPKG: {result['target_gpkg']}")
    if result['output_qgz']:
        print(f"Ziel-QGZ: {result['output_qgz']}")
    if result['report_path']:
        print(f"Report: {result['report_path']}")
    if result['archived_files']:
        print(f"Archiv: {os.path.dirname(result['archived_files'][0])} ({len(result['archived_files'])} Datei(en))")

    if result['skipped_layers']:
        print('')
        print('Uebersprungene Dateien:')
        for item in result['skipped_layers'][:10]:
            print(item)

    if result['failed_layers']:
        print('')
        print('Fehler:')
        for item in result['failed_layers'][:10]:
            print(item)


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Headless Kataster converter (PyQGIS).')
    parser.add_argument('--source', required=True, help='Path to source folder with shapefiles')
    parser.add_argument('--target', help='Path to target GPKG file (.gpkg)')
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    source_folder = os.path.normpath(args.source)
    target_gpkg = os.path.normpath(args.target) if args.target else default_output_path(source_folder)

    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        result = convert(source_folder, target_gpkg)
        print_summary(result)
        return 1 if result['failed_layers'] else 0
    finally:
        qgs.exitQgis()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as err:
        print(f'Fatal: {err}', file=sys.stderr)
        sys.exit(2)
