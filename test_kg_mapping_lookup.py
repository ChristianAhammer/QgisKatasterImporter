import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import kg_mapping_lookup as kg_lookup


class KgMappingLookupTests(unittest.TestCase):
    def test_parse_mapping_csv_semicolon_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "kg_mapping.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "KG_NUMMER;KG_NAME",
                        "51235;Strass",
                        "51235;DuplicateNameMustBeIgnored",
                        "abcd;Invalid",
                        "46144; Peterskirchen ",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            mapping = kg_lookup.parse_mapping_csv(csv_path)

            self.assertEqual(mapping["51235"], "Strass")
            self.assertEqual(mapping["46144"], "Peterskirchen")
            self.assertEqual(len(mapping), 2)

    def test_parse_mapping_csv_comma_header_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "custom.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "KG-Nr.,Katastralgemeinde Name",
                        "01004,Innere Stadt",
                        "01010,Neubau",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            mapping = kg_lookup.parse_mapping_csv(csv_path)

            self.assertEqual(mapping["01004"], "Innere Stadt")
            self.assertEqual(mapping["01010"], "Neubau")

    def test_discover_files_ignores_legacy_kg_lookup_cache_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_kg_lookup_cache").mkdir(parents=True, exist_ok=True)
            (root / "_kg_lookup_cache" / "katastralgemeindenverzeichnis.csv").write_text(
                "KG_NUMMER;KG_NAME\n99999;Legacy\n",
                encoding="utf-8",
            )
            preferred_csv = root / "kg_mapping.csv"
            preferred_csv.write_text("KG_NUMMER;KG_NAME\n51235;Strass\n", encoding="utf-8")

            csv_path, zip_path = kg_lookup.discover_files(root)

            self.assertEqual(csv_path, preferred_csv)
            self.assertIsNone(zip_path)

    def test_resolve_mapping_source_extracts_csv_from_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "KG_Verzeichnis.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("docs/readme.csv", "A;B\n1;2\n")
                archive.writestr(
                    "data/KGVZ_20250312.csv",
                    "KG_NUMMER;KG_NAME\n51235;Strass\n46144;Peterskirchen\n",
                )

            mapping_csv, extracted_from = kg_lookup.resolve_mapping_source(root, explicit_mapping=None)

            self.assertTrue(mapping_csv.is_file())
            self.assertEqual(extracted_from, zip_path)
            parsed = kg_lookup.parse_mapping_csv(mapping_csv)
            self.assertEqual(parsed["51235"], "Strass")

    def test_clean_path_arg_strips_wrapping_quotes(self):
        self.assertEqual(kg_lookup.clean_path_arg('"C:\\Temp\\file.csv"'), "C:\\Temp\\file.csv")
        self.assertEqual(kg_lookup.clean_path_arg("'C:\\Temp\\file.csv'"), "C:\\Temp\\file.csv")
        self.assertEqual(kg_lookup.clean_path_arg("C:\\Temp\\file.csv"), "C:\\Temp\\file.csv")


if __name__ == "__main__":
    unittest.main()
