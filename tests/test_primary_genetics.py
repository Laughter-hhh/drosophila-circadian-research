import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_primary_genetics import validate


FIELDS = [
    "paper_id", "reported_genotype", "driver", "effector", "cell_scope",
    "temperature_C", "LD_schedule", "free_running_condition", "experimental_unit",
    "n", "readout", "source_url", "evidence_level", "genotype_completeness", "notes",
]


class PrimaryGeneticsTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def test_construct_level_row_is_verified_with_warning(self):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "paper_id": "Griffith2008", "reported_genotype": "tim-GAL4/UAS-Shaw",
            "temperature_C": "25", "n": "39", "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2386553/",
            "genotype_completeness": "construct-level only",
        })
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_primary_genetics")
        self.assertTrue(result["warnings"])

    def test_nonpositive_n_is_rejected(self):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "paper_id": "Griffith2008", "temperature_C": "25", "n": "0",
            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2386553/",
            "genotype_completeness": "construct-level only",
        })
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_primary_genetics")
        self.assertTrue(any(issue.get("field") == "n" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
