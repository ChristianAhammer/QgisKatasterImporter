# test_qgis_integration.py - Test QGIS integration of refactored bev_to_qfield.py
import os, sys

# Add QGIS paths
QGIS_PREFIX = os.environ.get("QGIS_PREFIX_PATH", r"C:\OSGeo4W\apps\qgis")
QGIS_PY = os.path.join(QGIS_PREFIX, "python")
QGIS_PLUG = os.path.join(QGIS_PY, "plugins")
for p in (QGIS_PY, QGIS_PLUG):
    if p not in sys.path:
        sys.path.append(p)

print(f"✓ QGIS_PREFIX: {QGIS_PREFIX}")
print(f"✓ QGIS_PY: {QGIS_PY}")
print(f"✓ QGIS_PLUG: {QGIS_PLUG}")

# Test QGIS imports
try:
    from qgis.core import (
        QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
        QgsCoordinateReferenceSystem, QgsVectorFileWriter,
        QgsCoordinateTransformContext, QgsProviderRegistry,
        QgsWkbTypes, QgsProcessingFeedback,
        QgsFillSymbol, QgsSingleSymbolRenderer
    )
    print("✓ QGIS core imports successful")
except ImportError as e:
    print(f"✗ QGIS core import failed: {e}")
    sys.exit(1)

# Test PyQt5 imports
try:
    from PyQt5.QtWidgets import QFileDialog
    print("✓ PyQt5 imports successful")
except ImportError as e:
    print(f"✗ PyQt5 import failed: {e}")
    sys.exit(1)

# Test processing imports
try:
    import processing
    from processing.core.Processing import Processing
    print("✓ Processing imports successful")
except ImportError as e:
    print(f"✗ Processing import failed: {e}")
    sys.exit(1)

# Initialize QGIS
try:
    QgsApplication.setPrefixPath(QGIS_PREFIX, True)
    qgs = QgsApplication([], True)
    qgs.initQgis()
    Processing.initialize()
    print("✓ QGIS application initialized")
except Exception as e:
    print(f"✗ QGIS initialization failed: {e}")
    sys.exit(1)

# Now try to import our refactored module
try:
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    from bev_to_qfield import BEVToQFieldConfig, BEVToQField
    print("✓ bev_to_qfield module imports successful")
except ImportError as e:
    print(f"✗ Module import failed: {e}")
    qgs.exitQgis()
    sys.exit(1)

# Test BEVToQFieldConfig instantiation
try:
    base_path = r"C:\Users\Christian\Meine Ablage (ca19770610@gmail.com)\QGIS"
    config = BEVToQFieldConfig(base_path)
    print(f"✓ BEVToQFieldConfig instantiated")
    print(f"  - Base: {config.base}")
    print(f"  - Output dir: {config.dir_out}")
    print(f"  - Grids dir: {config.dir_grids}")
    print(f"  - Temp dir: {config.run_temp_dir}")
except Exception as e:
    print(f"✗ BEVToQFieldConfig instantiation failed: {e}")
    qgs.exitQgis()
    sys.exit(1)

# Test BEVToQField instantiation
try:
    converter = BEVToQField(config)
    print(f"✓ BEVToQField instantiated")
    print(f"  - Source CRS: {converter.config.SRC_CRS}")
    print(f"  - Target CRS: {converter.config.TGT_CRS}")
    print(f"  - Feedback: {converter.feedback}")
except Exception as e:
    print(f"✗ BEVToQField instantiation failed: {e}")
    qgs.exitQgis()
    sys.exit(1)

# Test helper methods
try:
    # Test _safe_name (dots and special chars are replaced with underscores)
    test_name = "BEV_Kataster_2025.shp"
    safe = converter._safe_name(test_name)
    assert safe == "BEV_Kataster_2025_shp", f"Safe name failed: {safe}"
    print(f"✓ _safe_name() works: '{test_name}' → '{safe}'")
    
    # Test _find_ntv2_grid (should return None if grids don't exist)
    ntv2 = converter._find_ntv2_grid()
    print(f"✓ _find_ntv2_grid() works: {'Found' if ntv2 else 'None (expected)'}")
    
    # Test _find_geoid (should return None if grids don't exist)
    geoid = converter._find_geoid()
    print(f"✓ _find_geoid() works: {'Found' if geoid else 'None (expected)'}")
    
except Exception as e:
    print(f"✗ Helper methods failed: {e}")
    qgs.exitQgis()
    sys.exit(1)

# Test CRS operations
try:
    src_crs = QgsCoordinateReferenceSystem(config.SRC_CRS)
    tgt_crs = QgsCoordinateReferenceSystem(config.TGT_CRS)
    assert src_crs.isValid(), "Source CRS invalid"
    assert tgt_crs.isValid(), "Target CRS invalid"
    print(f"✓ CRS operations work")
    print(f"  - Source: {src_crs.authid()} ({src_crs.description()})")
    print(f"  - Target: {tgt_crs.authid()} ({tgt_crs.description()})")
except Exception as e:
    print(f"✗ CRS operations failed: {e}")
    qgs.exitQgis()
    sys.exit(1)

# Cleanup
try:
    qgs.exitQgis()
    print("\n✓ All QGIS integration tests PASSED!")
    print("✓ QGIS cleanup successful")
except Exception as e:
    print(f"✗ Cleanup failed: {e}")
    sys.exit(1)
