import os
import unittest

from kataster_common import (
    dedupe_paths,
    default_output_path,
    is_kataster_shapefile,
    path_action,
    qgis_base_from_source,
    qgis_base_from_target,
)


class KatasterCommonTests(unittest.TestCase):
    def test_dedupe_paths_ignores_empty_and_case_duplicates(self):
        values = [
            "",
            None,
            r"C:\Data\Grid\..\Grid\NTv2.gsb",
            r"c:\data\grid\NTv2.gsb",
            r"C:\Data\Other\Grid.gsb",
        ]
        self.assertEqual(
            dedupe_paths(values),
            [
                os.path.normpath("C:/Data/Grid/NTv2.gsb"),
                os.path.normpath("C:/Data/Other/Grid.gsb"),
            ],
        )

    def test_qgis_base_from_source(self):
        path = r"C:\Users\Example\QGIS\01_BEV_Rawdata\44106"
        self.assertEqual(
            qgis_base_from_source(path),
            os.path.normpath("C:/Users/Example/QGIS"),
        )
        legacy_path = r"C:\Users\Example\QGIS\01_BEV_Rohdaten\44106"
        self.assertEqual(
            qgis_base_from_source(legacy_path),
            os.path.normpath("C:/Users/Example/QGIS"),
        )
        self.assertIsNone(qgis_base_from_source(r"C:\tmp\raw_data"))

    def test_qgis_base_from_target(self):
        path = r"C:\Users\Example\QGIS\03_QField_Output\kataster_44106_qfield.gpkg"
        self.assertEqual(
            qgis_base_from_target(path),
            os.path.normpath("C:/Users/Example/QGIS"),
        )
        self.assertIsNone(qgis_base_from_target(r"C:\tmp\out.gpkg"))

    def test_default_output_path_for_bev_structure(self):
        source = r"C:\Users\Example\QGIS\01_BEV_Rawdata\44106"
        expected = os.path.normpath(
            "C:/Users/Example/QGIS/03_QField_Output/kataster_44106_qfield/kataster_44106_qfield.gpkg"
        )
        self.assertEqual(default_output_path(source), expected)

    def test_default_output_path_fallback(self):
        source = r"C:\tmp\input_folder"
        expected = os.path.normpath(
            "C:/tmp/input_folder/kataster_input_folder_qfield/kataster_input_folder_qfield.gpkg"
        )
        self.assertEqual(default_output_path(source), expected)

    def test_is_kataster_shapefile(self):
        self.assertTrue(is_kataster_shapefile("44106GST_V2.shp"))
        self.assertTrue(is_kataster_shapefile("sgg.shp"))
        self.assertFalse(is_kataster_shapefile("segment.shp"))
        self.assertFalse(is_kataster_shapefile("notes.txt"))

    def test_path_action(self):
        created = path_action(False, r"C:\out\result.gpkg", "Datei")
        updated = path_action(True, r"C:\out\result.gpkg", "Datei")
        self.assertEqual(created["action"], "Erstellt")
        self.assertEqual(updated["action"], "Aktualisiert")
        self.assertIsNone(path_action(True, "", "Datei"))


if __name__ == "__main__":
    unittest.main()
