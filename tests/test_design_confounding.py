import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_design_confounding import inspect  # noqa: E402


class DesignConfoundingTests(unittest.TestCase):
    def test_perfectly_confounded_factors_are_not_declared_estimable(self):
        fields = ["sex", "background", "ZT_or_CT"]
        rows = [
            {"sex": "male_and_female", "background": "yw", "ZT_or_CT": "ZT0"},
            {"sex": "male_and_female", "background": "yw", "ZT_or_CT": "ZT12"},
            {"sex": "male", "background": "per01", "ZT_or_CT": "ZT0"},
            {"sex": "male", "background": "per01", "ZT_or_CT": "ZT12"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            path = Path(handle.name)
        try:
            result = inspect(path, ["sex", "background", "ZT_or_CT"])
        finally:
            path.unlink(missing_ok=True)

        pair = next(pair for pair in result["pair_reports"] if {pair["factor_a"], pair["factor_b"]} == {"sex", "background"})
        self.assertTrue(pair["perfectly_confounded"])
        self.assertEqual(result["status"], "warning")
        self.assertIn("not estimable", pair["warnings"][0])

    def test_real_gse22308_sex_background_pair_is_flagged(self):
        path = ROOT / "validation" / "public-data" / "GSE22308_sample_metadata.csv"
        result = inspect(path, ["sex", "genotype_background"])
        pair = result["pair_reports"][0]
        self.assertTrue(pair["perfectly_confounded"])
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["n_rows"], 24)

    def test_blank_factor_is_explicitly_reported(self):
        fields = ["sex", "background"]
        rows = [{"sex": "", "background": "yw"}, {"sex": "male", "background": "per01"}]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            path = Path(handle.name)
        try:
            result = inspect(path, fields)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["missing_counts"]["sex"], 1)
        self.assertFalse(result["pair_reports"][0]["perfectly_confounded"])
        self.assertEqual(result["status"], "warning")

    def test_absolute_input_path_is_rendered_portably(self):
        fields = ["sex", "background"]
        rows = [{"sex": "male", "background": "yw"}, {"sex": "female", "background": "yw"}]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            path = Path(handle.name).resolve()
        try:
            result = inspect(path, fields)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["input"], path.name)


if __name__ == "__main__":
    unittest.main()
