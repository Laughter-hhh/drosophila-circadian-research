import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_cross_plan import REQUIRED, validate


class CrossPlanTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _valid_row(self):
        return {
            "cross_id": "pilot-01",
            "purpose": "adult-restricted RNAi feasibility",
            "virgin_parent_sex": "female",
            "virgin_parent_genotype": "SYNTHETIC_driver; tub-GAL80ts/TM6B",
            "virgin_parent_stock": "SYNTHETIC-STOCK-A",
            "other_parent_sex": "male",
            "other_parent_genotype": "SYNTHETIC_UAS-RNAi/CyO",
            "other_parent_stock": "SYNTHETIC-STOCK-B",
            "f1_target_genotype": "SYNTHETIC_driver/+; tub-GAL80ts/+; UAS-RNAi/+",
            "balancer_or_selection": "TM6B and CyO markers",
            "reciprocal_cross": "planned",
            "background_control": "driver-only and UAS-RNAi-only siblings",
            "temperature_C": "18",
            "LD_schedule": "12:12 LD",
            "timeline_days": "14",
            "stock_source_urls": "https://flybase.org/; https://bdsc.indiana.edu/",
        }

    def test_complete_cross_is_verified(self):
        path = self._write(self._valid_row())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_cross_plan")
        self.assertEqual(result["issues"], [])

    def test_missing_balancer_and_background_are_rejected(self):
        row = self._valid_row()
        row["balancer_or_selection"] = "NA"
        row["background_control"] = "NA"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_cross_plan")
        missing = {(issue.get("column"), issue["type"]) for issue in result["issues"]}
        self.assertIn(("balancer_or_selection", "missing_required_field"), missing)
        self.assertIn(("background_control", "missing_required_field"), missing)


if __name__ == "__main__":
    unittest.main()
