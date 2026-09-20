import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_experiment_metadata import validate


FIELDS = [
    "species", "genotype", "sex", "age_days", "temperature_C", "lighting", "ZT_or_CT", "experimental_unit",
    "biological_replicate_id", "batch_id", "preparation", "cell_type", "recording_id", "technical_replicate_id",
]


class ExperimentMetadataTests(unittest.TestCase):
    def _write(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _row(self, index=1):
        return {
            "species": "Drosophila melanogaster", "genotype": "w1118", "sex": "female", "age_days": "5", "temperature_C": "25",
            "lighting": "LD 12:12", "ZT_or_CT": f"ZT{(index * 6) % 24}", "experimental_unit": "cell", "biological_replicate_id": f"fly{index}",
            "batch_id": "patch_batch_1", "preparation": "ex vivo whole brain", "cell_type": "s-LNv", "recording_id": f"rec{index}", "technical_replicate_id": f"trace{index}",
        }

    def test_complete_ephys_metadata_is_verified(self):
        path = self._write([self._row(i) for i in range(1, 5)])
        try:
            result = validate(path, assay="ephys", stage="formal")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_metadata")
        self.assertEqual(result["n_biological_replicates"], 4)
        self.assertEqual(len(result["input_file_metadata"]["sha256"]), 64)

    def test_formal_missing_high_impact_field_is_blocked(self):
        row = self._row(1)
        row["temperature_C"] = "unknown"
        path = self._write([row, self._row(2), self._row(3)])
        try:
            result = validate(path, assay="ephys", stage="formal")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_metadata_schema")
        self.assertTrue(any(issue["field"] == "temperature_C" for issue in result["issues"]))

    def test_exploratory_missing_high_impact_field_is_warning(self):
        row = self._row(1)
        row["sex"] = "unknown"
        path = self._write([row, self._row(2)])
        try:
            result = validate(path, assay="ephys", stage="exploratory")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_metadata")
        self.assertTrue(any(issue["field"] == "sex" for issue in result["warnings"]))

    def test_conflicting_metadata_within_biological_replicate_is_blocked(self):
        row1 = self._row(1)
        row2 = self._row(1)
        row2["temperature_C"] = "29"
        row2["recording_id"] = "rec1b"
        path = self._write([row1, row2, self._row(2)])
        try:
            result = validate(path, assay="ephys", stage="exploratory")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_metadata_schema")
        self.assertTrue(any(issue["type"] == "biological_replicate_metadata_conflict" for issue in result["issues"]))

    def test_public_synthetic_ephys_metadata_is_verified(self):
        path = ROOT / "validation" / "synthetic-ephys-metadata.csv"
        result = validate(path, assay="ephys", stage="formal")
        self.assertEqual(result["status"], "verified_metadata")
        self.assertEqual(result["n_biological_replicates"], 4)


if __name__ == "__main__":
    unittest.main()
