import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_source_access_report import validate


class SourceAccessReportTests(unittest.TestCase):
    def _write(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(payload, handle)
        handle.close()
        return Path(handle.name)

    def test_automated_verified_record_requires_trace_fields(self):
        path = self._write({
            "status": "verified_source_access",
            "records": [{
                "record_id": "stock-1",
                "source_url": "https://example.org/stock",
                "access_status": "reachable_content_verified",
                "http_status": 200,
                "matched_tokens": ["FBst1"],
                "body_sha256": "abc",
            }],
        })
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_source_access_report")

    def test_manual_verified_record_requires_observation_provenance(self):
        path = self._write({
            "status": "verified_source_access",
            "records": [{
                "record_id": "stock-1",
                "source_url": "https://flybase.org/reports/FBst1",
                "access_status": "reachable_content_verified",
                "verification_method": "browser_manual",
                "checked_at_utc": "2026-09-08T10:00:00+00:00",
                "observed_tokens": ["FBst1", "80939"],
                "observation_note": "Browser view showed the stock ID and listed genotype.",
            }],
        })
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_source_access_report")

    def test_manual_verified_record_without_note_is_blocked(self):
        path = self._write({
            "status": "verified_source_access",
            "records": [{
                "record_id": "stock-1",
                "source_url": "https://flybase.org/reports/FBst1",
                "access_status": "reachable_content_verified",
                "verification_method": "browser_manual",
                "checked_at_utc": "2026-09-08T10:00:00+00:00",
                "observed_tokens": ["FBst1"],
            }],
        })
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_source_access_report")
        self.assertTrue(any(issue["type"] == "manual_verified_requires_observation_note" for issue in result["issues"]))

    def test_conditional_automated_report_is_schema_valid(self):
        path = self._write({
            "status": "conditional_source_access",
            "records": [{
                "record_id": "stock-1",
                "source_url": "https://flybase.org/reports/FBst1",
                "access_status": "reachable_content_unverified",
                "http_status": 202,
                "matched_tokens": [],
                "body_sha256": "challenge",
            }],
        })
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_source_access_report")
        self.assertEqual(result["report_status"], "conditional_source_access")

    def test_duplicate_records_are_rejected(self):
        path = self._write({
            "status": "verified_source_access",
            "records": [
                {"record_id": "same", "source_url": "https://example.org/a", "access_status": "reachable_content_unverified"},
                {"record_id": "same", "source_url": "https://example.org/b", "access_status": "reachable_content_unverified"},
            ],
        })
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_source_access_report")
        self.assertTrue(any(issue["type"] == "duplicate_record_id" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
