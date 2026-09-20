import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_hierarchy import inspect


class HierarchyTests(unittest.TestCase):
    def test_repeated_cells_are_reported_without_inflating_subject_count(self):
        fields = ["biological_replicate_id", "batch_id", "ZT_or_CT", "cell_id"]
        rows = [
            {"biological_replicate_id": "fly_01", "batch_id": "b1", "ZT_or_CT": "ZT0", "cell_id": "c1"},
            {"biological_replicate_id": "fly_01", "batch_id": "b1", "ZT_or_CT": "ZT0", "cell_id": "c2"},
            {"biological_replicate_id": "fly_02", "batch_id": "b1", "ZT_or_CT": "ZT0", "cell_id": "c3"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            path = Path(handle.name)
        try:
            result = inspect(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["n_biological_replicates"], 2)
        self.assertEqual(result["repeated_biological_replicates"], {"fly_01": 2})
        self.assertEqual(result["status"], "warning")

    def test_batch_time_confounding_is_reported(self):
        fields = ["biological_replicate_id", "batch_id", "ZT_or_CT"]
        rows = [
            {"biological_replicate_id": "fly_01", "batch_id": "b1", "ZT_or_CT": "ZT0"},
            {"biological_replicate_id": "fly_02", "batch_id": "b2", "ZT_or_CT": "ZT4"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            path = Path(handle.name)
        try:
            result = inspect(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertTrue(any("perfectly confounded" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
