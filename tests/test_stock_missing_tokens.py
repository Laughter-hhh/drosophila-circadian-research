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


class StockMissingTokenTests(unittest.TestCase):
    def test_placeholder_text_cannot_claim_verified_identity(self):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "candidate": "Pdf-GAL4", "flybase_id": "FBst0080939",
            "flybase_url": "https://flybase.org/reports/FBst0080939",
            "source_url": "https://bdsc.indiana.edu/", "source_checked_date": "2026-09-06",
            "genetic_background": "not specified", "verification_status": "identity_verified",
        })
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        path = Path(handle.name)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_stock_audit")
        self.assertTrue(any(
            issue.get("type") == "verified_identity_missing_field"
            and issue.get("field") == "genetic_background"
            for issue in result["issues"]
        ))


if __name__ == "__main__":
    unittest.main()
