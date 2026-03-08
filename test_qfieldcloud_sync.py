import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qfieldcloud_sync


class QFieldCloudSyncTests(unittest.TestCase):
    def test_redact_sensitive_data_scrubs_nested_credentials(self):
        payload = {
            "token": "abc",
            "nested": {
                "access_token": "def",
                "password": "secret",
                "safe": "ok",
            },
            "items": [{"authorization": "Bearer xyz"}],
        }

        redacted = qfieldcloud_sync.redact_sensitive_data(payload)

        self.assertEqual(redacted["token"], qfieldcloud_sync.REDACTED)
        self.assertEqual(redacted["nested"]["access_token"], qfieldcloud_sync.REDACTED)
        self.assertEqual(redacted["nested"]["password"], qfieldcloud_sync.REDACTED)
        self.assertEqual(redacted["nested"]["safe"], "ok")
        self.assertEqual(redacted["items"][0]["authorization"], qfieldcloud_sync.REDACTED)

    def test_write_summary_persists_redacted_output(self):
        summary = {"login_result": {"token": "abc123"}, "errors": []}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            qfieldcloud_sync.write_summary(str(path), summary)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["login_result"]["token"], qfieldcloud_sync.REDACTED)


if __name__ == "__main__":
    unittest.main()
