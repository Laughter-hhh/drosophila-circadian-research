import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_source_access import validate


class FakeResponse:
    def __init__(self, status=200, body=b"<html>FBst0080939 80939</html>", url="https://example.org/source"):
        self.status = status
        self._body = body
        self._url = url
        self.headers = {"Content-Type": "text/html"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, max_bytes):
        return self._body[:max_bytes]

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status


class SourceAccessTests(unittest.TestCase):
    def _write(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["record_id", "source_url", "expected_tokens"])
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def test_content_and_expected_token_are_verified(self):
        path = self._write([{
            "record_id": "stock-1",
            "source_url": "https://example.org/source",
            "expected_tokens": "FBst0080939;80939",
        }])
        try:
            with patch("scripts.check_source_access.urllib.request.urlopen", return_value=FakeResponse()):
                result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_source_access")
        self.assertEqual(result["records"][0]["access_status"], "reachable_content_verified")
        self.assertEqual(result["records"][0]["matched_tokens"], ["fbst0080939", "80939"])

    def test_reachable_challenge_page_is_conditional_not_verified(self):
        path = self._write([{
            "record_id": "stock-1",
            "source_url": "https://example.org/source",
            "expected_tokens": "FBst0080939",
        }])
        try:
            with patch(
                "scripts.check_source_access.urllib.request.urlopen",
                return_value=FakeResponse(status=202, body=b"challenge"),
            ):
                result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "conditional_source_access")
        self.assertEqual(result["formal_status"], "blocked_online_content_not_verified")
        self.assertEqual(result["records"][0]["access_status"], "reachable_content_unverified")

    def test_network_error_blocks_source_access(self):
        path = self._write([{
            "record_id": "paper-1",
            "source_url": "https://example.org/source",
            "expected_tokens": "PMID:31612994",
        }])
        try:
            with patch(
                "scripts.check_source_access.urllib.request.urlopen",
                side_effect=OSError("offline"),
            ):
                result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_source_access")
        self.assertEqual(result["formal_status"], "blocked_by_online_access")
        self.assertEqual(result["issues"][0]["type"], "source_not_reachable")

    def test_manifest_rejects_duplicate_and_credential_urls(self):
        path = self._write([
            {"record_id": "same", "source_url": "https://user:pass@example.org/a", "expected_tokens": "x"},
            {"record_id": "same", "source_url": "https://example.org/b", "expected_tokens": "x"},
        ])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_source_access")
        self.assertTrue(any(issue["type"] == "invalid_source_url" for issue in result["issues"]))
        self.assertTrue(any(issue["type"] == "duplicate_record_id" for issue in result["issues"]))

    def test_public_schema_is_machine_readable(self):
        path = self._write([{
            "record_id": "record-1",
            "source_url": "https://example.org/source",
            "expected_tokens": "ID-1",
        }])
        try:
            with patch("scripts.check_source_access.urllib.request.urlopen", return_value=FakeResponse(body=b"ID-1")):
                result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["n_records"], 1)


if __name__ == "__main__":
    unittest.main()
