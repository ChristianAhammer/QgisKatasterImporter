import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import extract_kg_from_zip


class ExtractKgFromZipTests(unittest.TestCase):
    def test_extract_matching_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "data.zip"
            out_root = root / "out"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("docs/readme.txt", "ignore")
                archive.writestr("nested/51235/gst_demo.shp", "shape")
                archive.writestr("nested/51235/subdir/info.txt", "info")

            found = extract_kg_from_zip.extract_matching_folder(zip_path, out_root, "51235")

            self.assertTrue(found)
            self.assertEqual((out_root / "51235" / "gst_demo.shp").read_text(encoding="utf-8"), "shape")
            self.assertEqual((out_root / "51235" / "subdir" / "info.txt").read_text(encoding="utf-8"), "info")

    def test_extract_from_zip_root_returns_false_when_folder_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "data.zip"
            out_root = root / "out"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("nested/99999/gst_demo.shp", "shape")

            found = extract_kg_from_zip.extract_from_zip_root(root, out_root, "51235")

            self.assertFalse(found)
            self.assertFalse((out_root / "51235").exists())

    def test_extract_matching_folder_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "data.zip"
            out_root = root / "out"
            escaped = root / "escape.txt"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("nested/51235/../escape.txt", "bad")

            with self.assertRaises(extract_kg_from_zip.UnsafeZipPathError):
                extract_kg_from_zip.extract_matching_folder(zip_path, out_root, "51235")

            self.assertFalse(escaped.exists())


if __name__ == "__main__":
    unittest.main()
