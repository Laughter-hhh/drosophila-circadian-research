import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_preanalysis_bundle import validate_bundle


class PreanalysisBundleTests(unittest.TestCase):
    def test_public_synthetic_bundle_is_verified(self):
        result = validate_bundle(
            ROOT / "validation" / "synthetic-ephys-bundle-metadata.csv",
            ROOT / "validation" / "synthetic-ephys-raw-qc.csv",
            ROOT / "validation" / "synthetic-ephys-derived-measurements.csv",
            assay="ephys", stage="formal", check_files=True,
        )
        self.assertEqual(result["status"], "verified_preanalysis_bundle")
        self.assertEqual(result["n_pass_raw_records"], 2)
        self.assertEqual(result["n_measurement_rows"], 2)
        self.assertEqual(len(result["input_file_metadata"]["measurements"]["sha256"]), 64)

    def test_orphan_measurement_blocks_bundle(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["record_id", "metadata_row_id", "biological_replicate_id", "time_hours", "value"])
        writer.writeheader()
        writer.writerow({"record_id": "orphan", "metadata_row_id": "meta01", "biological_replicate_id": "fly01", "time_hours": "2", "value": "1"})
        handle.close()
        try:
            result = validate_bundle(
                ROOT / "validation" / "synthetic-ephys-bundle-metadata.csv",
                ROOT / "validation" / "synthetic-ephys-raw-qc.csv",
                Path(handle.name), assay="ephys", stage="formal", check_files=True,
            )
        finally:
            Path(handle.name).unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_preanalysis_bundle")
        self.assertTrue(any(issue["type"] == "orphan_measurement_record" for issue in result["issues"]))

    def test_measurement_from_excluded_raw_record_is_blocked(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["record_id", "metadata_row_id", "biological_replicate_id", "time_hours", "value"])
        writer.writeheader()
        writer.writerow({"record_id": "rec03", "metadata_row_id": "meta03", "biological_replicate_id": "fly03", "time_hours": "14", "value": "1"})
        handle.close()
        try:
            result = validate_bundle(
                ROOT / "validation" / "synthetic-ephys-bundle-metadata.csv",
                ROOT / "validation" / "synthetic-ephys-raw-qc.csv",
                Path(handle.name), assay="ephys", stage="exploratory", check_files=True,
            )
        finally:
            Path(handle.name).unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_preanalysis_bundle")
        self.assertTrue(any(issue["type"] == "measurement_from_nonpass_raw_record" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
