#!/usr/bin/env python3
"""Headless Kataster converter using PyQGIS.

Run via QGIS Python environment (e.g. python-qgis-ltr.bat):
    python kataster_converter_cli.py --source <folder> [--target <path.gpkg>]
"""

import argparse
import datetime
import glob
import json
import math
import os
import re
import shutil
import sqlite3
import sys


def _bootstrap_processing_paths():
    candidates = []

    qgis_prefix = os.environ.get('QGIS_PREFIX_PATH')
    if qgis_prefix:
        candidates.append(qgis_prefix)

    osgeo4w_root = os.environ.get('OSGEO4W_ROOT', r'C:\OSGeo4W')
    candidates.append(os.path.join(osgeo4w_root, 'apps', 'qgis'))
    candidates.append(os.path.join(osgeo4w_root, 'apps', 'qgis-ltr'))

    seen = set()
    for prefix in candidates:
        if not prefix:
            continue
        norm_prefix = os.path.normpath(prefix)
        key = norm_prefix.lower()
        if key in seen:
            continue
        seen.add(key)
        for sub in (os.path.join(norm_prefix, 'python'), os.path.join(norm_prefix, 'python', 'plugins')):
            if os.path.isdir(sub) and sub not in sys.path:
                sys.path.append(sub)


_bootstrap_processing_paths()
try:
    import processing
    from processing.core.Processing import Processing
    PROCESSING_IMPORT_ERROR = None
except ModuleNotFoundError as err:
    processing = None
    Processing = None
    PROCESSING_IMPORT_ERROR = err

from qgis.core import (
    QgsApplication,
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

ORTHOFOTO_LAYER_NAME = 'BEV Orthofoto (basemap.at)'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
COLOR_RED = '\033[31m'
COLOR_RESET = '\033[0m'


def _dedupe_paths(values):
    unique = []
    seen = set()
    for raw in values:
        if not raw:
            continue
        norm = os.path.normpath(raw)
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(norm)
    return unique


def _qgis_base_from_source(source_folder):
    match = re.search(r'^(.*?)[\\/]01_bev_rohdaten(?:[\\/].*)?$', os.path.normpath(source_folder), flags=re.IGNORECASE)
    if not match:
        return None
    return os.path.normpath(match.group(1))


def _qgis_base_from_target(target_gpkg):
    match = re.search(r'^(.*?)[\\/]03_qfield_output(?:[\\/].*)?$', os.path.normpath(target_gpkg), flags=re.IGNORECASE)
    if not match:
        return None
    return os.path.normpath(match.group(1))


def _detail_value(obj, attr, default=None):
    if not hasattr(obj, attr):
        return default
    value = getattr(obj, attr)
    try:
        return value() if callable(value) else value
    except Exception:
        return default


def select_gisgrid_operation(crs_source, crs_target):
    transform = QgsCoordinateTransform(crs_source, crs_target, QgsCoordinateTransformContext())
    if not hasattr(transform, 'instantiatedCoordinateOperationDetails'):
        return None, None, None, [], 'QGIS API liefert keine OperationDetails fuer die Transformationspruefung.'

    details = transform.instantiatedCoordinateOperationDetails()
    operation = _detail_value(details, 'proj', '') or ''
    operation_name = _detail_value(details, 'name', '') or ''
    operation_accuracy = _detail_value(details, 'accuracy', None)
    is_available = bool(_detail_value(details, 'isAvailable', False))
    grids = _detail_value(details, 'grids', []) or []

    available_grids = []
    for grid in grids:
        grid_available = bool(_detail_value(grid, 'isAvailable', True))
        grid_path = _detail_value(grid, 'fullName', '') or _detail_value(grid, 'shortName', '')
        if grid_available and grid_path:
            available_grids.append(grid_path)

    if not is_available:
        return None, None, None, available_grids, 'QGIS meldet die bevorzugte GIS-Grid Transformation als nicht verfuegbar.'
    if 'hgridshift' not in operation.lower():
        return None, None, None, available_grids, 'Die aktive Transformation nutzt kein hgridshift/GIS-Grid.'
    if not available_grids:
        return None, None, None, available_grids, 'Kein verfuegbares GIS-Grid in der aktiven Transformation gefunden.'

    return operation, operation_name, operation_accuracy, available_grids, None


def find_ntv2_grid(source_folder, target_gpkg, explicit_grid=None):
    direct_candidates = [explicit_grid]
    for env_key in ('QGIS_GISGRID_GSB', 'GISGRID_GSB', 'NTV2_GRID_PATH'):
        direct_candidates.append(os.environ.get(env_key))

    for candidate in _dedupe_paths(direct_candidates):
        if os.path.isfile(candidate) and candidate.lower().endswith('.gsb'):
            return candidate, [candidate]

    search_dirs = []
    processing_root = os.environ.get('QFC_PROCESSING_ROOT')
    if processing_root:
        search_dirs.append(os.path.join(processing_root, 'grids'))

    qgis_base_from_source = _qgis_base_from_source(source_folder)
    if qgis_base_from_source:
        search_dirs.append(os.path.join(qgis_base_from_source, '02_QGIS_Processing', 'grids'))

    qgis_base_from_target = _qgis_base_from_target(target_gpkg)
    if qgis_base_from_target:
        search_dirs.append(os.path.join(qgis_base_from_target, '02_QGIS_Processing', 'grids'))

    searched = _dedupe_paths(search_dirs)
    for search_dir in searched:
        if not os.path.isdir(search_dir):
            continue
        matches = sorted(glob.glob(os.path.join(search_dir, '**', '*.gsb'), recursive=True))
        if matches:
            return os.path.normpath(matches[0]), searched

    return None, searched


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


def build_orthofoto_layer():
    wmts_params = {
        'contextualWMSLegend': '0',
        'crs': 'EPSG:3857',
        'dpiMode': '7',
        'format': 'image/jpeg',
        'layers': 'bmaporthofoto30cm',
        'styles': 'normal',
        'tileMatrixSet': 'google3857',
        'url': 'https://www.basemap.at/wmts/1.0.0/WMTSCapabilities.xml',
    }
    wmts_uri = '&'.join(f'{key}={value}' for key, value in wmts_params.items())

    ortho = QgsRasterLayer(wmts_uri, ORTHOFOTO_LAYER_NAME, 'wms')
    if not ortho.isValid():
        return None

    ortho.setOpacity(1.0)
    return ortho


def move_layer_to_bottom(project, layer_id):
    root = project.layerTreeRoot()
    node = root.findLayer(layer_id)
    if not node:
        return

    parent = node.parent() or root
    clone = node.clone()
    parent.removeChildNode(node)
    parent.addChildNode(clone)


def ensure_orthofoto_layer(project):
    for layer in project.mapLayers().values():
        if isinstance(layer, QgsRasterLayer) and layer.name() == ORTHOFOTO_LAYER_NAME:
            move_layer_to_bottom(project, layer.id())
            return

    ortho = build_orthofoto_layer()
    if ortho and ortho.isValid():
        project.addMapLayer(ortho)
        move_layer_to_bottom(project, ortho.id())


def write_output_project(gpkg_path, layer_names, target_crs):
    output_qgz = os.path.splitext(gpkg_path)[0] + '.qgz'
    output_project = QgsProject()
    output_project.setFileName(output_qgz)
    output_project.setCrs(target_crs)
    ensure_orthofoto_layer(output_project)

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

    ensure_orthofoto_layer(output_project)

    if not output_project.write():
        return None, 'QGIS-Projektdatei konnte nicht geschrieben werden'

    return output_qgz, None


def write_report(report_path, source_folder, target_gpkg, output_qgz, ntv2_grid, imported_layers, skipped_layers, failed_layers):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        f'Kataster-Konverter Report: {timestamp}',
        f'Quelle: {source_folder}',
        f'Ziel-GPKG: {target_gpkg}',
        f'Ziel-QGZ: {output_qgz or "nicht erstellt"}',
        f'GIS-Grid: {ntv2_grid or "nicht gefunden"}',
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


def _path_action(existed_before, path, kind):
    if not path:
        return None
    action = 'Aktualisiert' if existed_before else 'Erstellt'
    return {'action': action, 'kind': kind, 'path': os.path.normpath(path)}


def convert(source_folder, target_gpkg, ntv2_grid_path=None):
    if not os.path.isdir(source_folder):
        raise RuntimeError(f'Quellordner nicht gefunden: {source_folder}')

    target_gpkg = os.path.normpath(target_gpkg)
    if not target_gpkg.lower().endswith('.gpkg'):
        target_gpkg += '.gpkg'

    gpkg_folder = os.path.dirname(target_gpkg)
    gpkg_folder_existed_before = os.path.isdir(gpkg_folder)
    os.makedirs(gpkg_folder, exist_ok=True)

    if not os.access(gpkg_folder, os.W_OK):
        raise RuntimeError(f'Kein Schreibzugriff auf Verzeichnis: {gpkg_folder}')

    crs_source = QgsCoordinateReferenceSystem('EPSG:31255')
    crs_target = QgsCoordinateReferenceSystem('EPSG:25833')
    ntv2_grid, searched_grid_dirs = find_ntv2_grid(source_folder, target_gpkg, ntv2_grid_path)
    if not ntv2_grid:
        searched_info = ', '.join(searched_grid_dirs) if searched_grid_dirs else 'keine Suchpfade ableitbar'
        raise RuntimeError(
            'GIS-Grid (*.gsb) nicht gefunden. Transformation wird aus Genauigkeitsgruenden abgebrochen. '
            f'Gesucht in: {searched_info}'
        )

    operation, operation_name, operation_accuracy, operation_grids, operation_error = select_gisgrid_operation(
        crs_source, crs_target
    )
    if operation_error:
        raise RuntimeError(
            f'{operation_error} Ausgewaehlte lokale GIS-Grid Datei: {ntv2_grid}'
        )
    transform_context = QgsCoordinateTransformContext()

    imported_layers = []
    skipped_layers = []
    failed_layers = []
    path_actions = []

    gpkg_exists = os.path.exists(target_gpkg)
    target_gpkg_existed_before = gpkg_exists
    output_qgz_path = os.path.splitext(target_gpkg)[0] + '.qgz'
    output_qgz_existed_before = os.path.exists(output_qgz_path)
    report_path = os.path.splitext(target_gpkg)[0] + '_report.txt'
    report_existed_before = os.path.exists(report_path)
    output_dir = os.path.dirname(target_gpkg)
    archive_dir = os.path.join(output_dir, 'archive')
    archive_dir_existed_before = os.path.isdir(archive_dir)

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

        try:
            reprojected = processing.run(
                'native:reprojectlayer',
                {
                    'INPUT': layer,
                    'TARGET_CRS': crs_target,
                    'OPERATION': operation,
                    'OUTPUT': 'TEMPORARY_OUTPUT',
                },
            )['OUTPUT']
        except Exception as err:
            failed_layers.append(f'{filename}: Reprojektion fehlgeschlagen ({err})')
            continue

        extent = reprojected.extent()
        extent_values = [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()]
        if not all(math.isfinite(value) for value in extent_values):
            failed_layers.append(f'{filename}: Reprojektion lieferte ungueltige Ausdehnung {extent_values}')
            continue

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.layerName = layer_name
        options.fileEncoding = 'UTF-8'
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
            failed_layers.append(f'{filename}: Exportfehler ({msg})')
            continue

        gpkg_exists = True

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

    try:
        write_report(
            report_path,
            source_folder,
            target_gpkg,
            output_qgz,
            ntv2_grid,
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

    if not gpkg_folder_existed_before and os.path.isdir(gpkg_folder):
        path_actions.append({'action': 'Erstellt', 'kind': 'Ordner', 'path': os.path.normpath(gpkg_folder)})

    gpkg_action = _path_action(target_gpkg_existed_before, target_gpkg, 'Datei')
    if gpkg_action and os.path.exists(target_gpkg):
        path_actions.append(gpkg_action)

    if output_qgz and os.path.exists(output_qgz):
        qgz_action = _path_action(output_qgz_existed_before, output_qgz, 'Datei')
        if qgz_action:
            path_actions.append(qgz_action)

    if report_path and os.path.exists(report_path):
        report_action = _path_action(report_existed_before, report_path, 'Datei')
        if report_action:
            path_actions.append(report_action)

    if archived_files:
        if not archive_dir_existed_before and os.path.isdir(archive_dir):
            path_actions.append({'action': 'Erstellt', 'kind': 'Ordner', 'path': os.path.normpath(archive_dir)})
        for archived_path in archived_files:
            path_actions.append({'action': 'Erstellt', 'kind': 'Datei', 'path': os.path.normpath(archived_path)})

    return {
        'target_gpkg': target_gpkg,
        'output_qgz': output_qgz,
        'report_path': report_path,
        'ntv2_grid': ntv2_grid,
        'operation_name': operation_name,
        'operation_accuracy': operation_accuracy,
        'operation_grid': operation_grids[0] if operation_grids else None,
        'imported_layers': imported_layers,
        'skipped_layers': skipped_layers,
        'failed_layers': failed_layers,
        'archived_files': archived_files,
        'path_actions': path_actions,
    }


def print_summary(result):
    color_enabled = sys.stdout.isatty() and os.environ.get('NO_COLOR') is None

    def colorize(text, color):
        if not color_enabled:
            return text
        return f'{color}{text}{COLOR_RESET}'

    imported_count = len(result['imported_layers'])
    skipped_count = len(result['skipped_layers'])
    failed_count = len(result['failed_layers'])

    print(colorize(f'Importiert: {imported_count} Layer', COLOR_GREEN))
    skipped_line = f'Uebersprungen: {skipped_count}'
    print(colorize(skipped_line, COLOR_YELLOW if skipped_count else COLOR_GREEN))
    failed_line = f'Fehlgeschlagen: {failed_count}'
    print(colorize(failed_line, COLOR_RED if failed_count else COLOR_GREEN))
    print('')
    print(f"Ziel-GPKG: {result['target_gpkg']}")
    if result.get('ntv2_grid'):
        print(f"GIS-Grid: {result['ntv2_grid']}")
    if result.get('operation_name'):
        print(f"Transform: {result['operation_name']}")
    if result.get('operation_grid'):
        print(f"Aktives Grid: {result['operation_grid']}")
    if result.get('operation_accuracy') is not None:
        print(f"Transform-Genauigkeit: {result['operation_accuracy']} m")
    if result['output_qgz']:
        print(f"Ziel-QGZ: {result['output_qgz']}")
    if result['report_path']:
        print(f"Report: {result['report_path']}")
    if result['archived_files']:
        print(f"Archiv: {os.path.dirname(result['archived_files'][0])} ({len(result['archived_files'])} Datei(en))")

    path_actions = result.get('path_actions') or []
    if path_actions:
        print('')
        print(colorize('Dateisystem-Aenderungen:', COLOR_GREEN))
        for item in path_actions:
            action = item.get('action', 'Aenderung')
            kind = item.get('kind', 'Pfad')
            path = item.get('path', '')
            line = f'{action} {kind}: {path}'
            if action == 'Erstellt':
                print(colorize(line, COLOR_GREEN))
            elif action == 'Aktualisiert':
                print(colorize(line, COLOR_YELLOW))
            else:
                print(line)

    if result['skipped_layers']:
        print('')
        print(colorize('Uebersprungene Dateien:', COLOR_YELLOW))
        for item in result['skipped_layers'][:10]:
            print(colorize(item, COLOR_YELLOW))

    if result['failed_layers']:
        print('')
        print(colorize('Fehler:', COLOR_RED))
        for item in result['failed_layers'][:10]:
            print(colorize(item, COLOR_RED))


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Headless Kataster converter (PyQGIS).')
    parser.add_argument('--source', required=True, help='Path to source folder with shapefiles')
    parser.add_argument('--target', help='Path to target GPKG file (.gpkg)')
    parser.add_argument('--ntv2-grid', help='Optional explicit path to GIS_Grid .gsb file')
    parser.add_argument('--summary-json', help='Optional output file for machine-readable summary json')
    parser.add_argument('--summary-target-file', help='Optional output file containing target_gpkg path')
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    source_folder = os.path.normpath(args.source)
    target_gpkg = os.path.normpath(args.target) if args.target else default_output_path(source_folder)

    qgs = QgsApplication([], False)
    qgs.initQgis()
    if processing is None or Processing is None:
        raise RuntimeError(
            f'QGIS Processing-Modul konnte nicht geladen werden: {PROCESSING_IMPORT_ERROR}. '
            'Bitte Processing-Plugin Installation prüfen.'
        )
    Processing.initialize()
    try:
        result = convert(source_folder, target_gpkg, ntv2_grid_path=args.ntv2_grid)
        print_summary(result)
        if args.summary_json:
            with open(args.summary_json, 'w', encoding='utf-8') as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
        if args.summary_target_file:
            with open(args.summary_target_file, 'w', encoding='utf-8') as handle:
                handle.write(result['target_gpkg'] + '\n')
        return 1 if result['failed_layers'] else 0
    finally:
        qgs.exitQgis()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as err:
        color_enabled = sys.stderr.isatty() and os.environ.get('NO_COLOR') is None
        if color_enabled:
            print(f'{COLOR_RED}Fatal: {err}{COLOR_RESET}', file=sys.stderr)
        else:
            print(f'Fatal: {err}', file=sys.stderr)
        sys.exit(2)
