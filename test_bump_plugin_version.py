import tempfile
import unittest
from pathlib import Path

from scripts import bump_plugin_version


class BumpPluginVersionTests(unittest.TestCase):
    def test_parse_version_accepts_supported_formats(self):
        self.assertEqual(bump_plugin_version.parse_version("1"), (1, 0, 0))
        self.assertEqual(bump_plugin_version.parse_version("1.2"), (1, 2, 0))
        self.assertEqual(bump_plugin_version.parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_rejects_invalid_format(self):
        with self.assertRaises(ValueError):
            bump_plugin_version.parse_version("1.2.beta")

    def test_bump_version(self):
        self.assertEqual(bump_plugin_version.bump_version("1"), "1.0.1")
        self.assertEqual(bump_plugin_version.bump_version("1.2"), "1.2.1")
        self.assertEqual(bump_plugin_version.bump_version("1.2.3"), "1.2.4")

    def test_bump_metadata_version_updates_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata_path = Path(tmp_dir) / "metadata.txt"
            metadata_path.write_text(
                "[general]\nname = Kataster Converter\nversion = 1.5.9\nauthor = Test\n",
                encoding="utf-8",
            )

            new_version = bump_plugin_version.bump_metadata_version(metadata_path)

            self.assertEqual(new_version, "1.5.10")
            content = metadata_path.read_text(encoding="utf-8")
            self.assertIn("version = 1.5.10", content)
            self.assertIn("name = Kataster Converter", content)

    def test_bump_metadata_version_requires_general_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata_path = Path(tmp_dir) / "metadata.txt"
            metadata_path.write_text("[general]\nname = Kataster Converter\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                bump_plugin_version.bump_metadata_version(metadata_path)


if __name__ == "__main__":
    unittest.main()
