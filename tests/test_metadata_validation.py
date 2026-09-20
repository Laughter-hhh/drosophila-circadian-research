import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_metadata import validate


class MetadataValidationTests(unittest.TestCase):
    def test_missing_circadian_time_is_reported(self):
        fields = [
            "species", "genotype", "sex", "age_days", "temperature_C", "lighting",
            "ZT_or_CT", "experimental_unit", "biological_replicate_id", "batch_id",
        ]
        row = {
            "species": "Drosophila melanogaster", "genotype": "w1118", "sex": "female",
            "age_days": "5", "temperature_C": "25", "lighting": "LD 12:12",
            "ZT_or_CT": "", "experimental_unit": "fly", "biological_replicate_id": "f1",
            "batch_id": "b1",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
            path = Path(handle.name)
        try:
            errors = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertTrue(any("ZT_or_CT" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
