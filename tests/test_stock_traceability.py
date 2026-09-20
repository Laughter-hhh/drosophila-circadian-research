import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_stock_audit import validate


FIELDS = [
    "candidate", "flybase_id", "flybase_url", "stock_center", "stock_number",
    "full_genotype", "insertion_chromosome", "genetic_background",
    "balancer_or_marker", "availability_status", "source_checked_date",
    "source_url", "verification_status", "notes",
]


class StockTraceabilityTests(unittest.TestCase):
    def _validate(self, url: str):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "candidate": "Shaw", "flybase_id": "FBgn0003386", "flybase_url": url,
            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2386553/",
            "source_checked_date": "2026-09-06", "verification_status": "identity_verified",
        })
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        path = Path(handle.name)
        try:
            return validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_flybase_url_id_mismatch_is_rejected(self):
        result = self._validate("https://flybase.org/reports/FBst0080939")
        self.assertEqual(result["status"], "invalid_stock_audit")
        self.assertTrue(any(issue.get("type") == "flybase_url_id_mismatch" for issue in result["issues"]))

    def test_matching_flybase_url_id_is_accepted(self):
        result = self._validate("https://flybase.org/reports/FBgn0003386")
        self.assertEqual(result["status"], "verified_stock_audit")


if __name__ == "__main__":
    unittest.main()
