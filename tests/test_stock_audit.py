import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_stock_audit import REQUIRED, validate


class StockAuditTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _row(self):
        return {
            "candidate": "Shaw", "flybase_id": "FBgn0003386",
            "flybase_url": "https://flybase.org/reports/FBgn0003386",
            "stock_center": "BDSC", "stock_number": "80939",
            "full_genotype": "documented", "insertion_chromosome": "2",
            "genetic_background": "documented", "balancer_or_marker": "none",
            "availability_status": "living stock", "source_checked_date": "2026-09-07",
            "source_url": "https://bdsc.indiana.edu/", "verification_status": "identity_verified",
            "notes": "documented",
        }

    def test_complete_identity_is_verified_but_external_checks_remain(self):
        path = self._write(self._row())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_stock_audit")
        self.assertEqual(result["formal_status"], "identity_gate_passed_external_checks_pending")
        self.assertEqual(result["n_identity_verified"], 1)

    def test_partial_identity_is_explicitly_blocked_for_formal_cross(self):
        row = self._row()
        row["verification_status"] = "partial"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_stock_audit")
        self.assertEqual(result["formal_status"], "blocked_identity_not_verified")
        self.assertEqual(result["n_identity_not_verified"], 1)

    def test_missing_genotype_blocks_verified_identity(self):
        row = self._row()
        row["full_genotype"] = "NA"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_stock_audit")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "missing_field" and issue.get("field") == "full_genotype" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
