import csv
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.prepare_mixed_model_input import prepare


class MixedModelNumericCovariateTests(unittest.TestCase):
    fields = [
        "biological_replicate_id", "time_hours", "value", "experimental_unit",
        "gene_symbol", "cell_type", "background", "batch_id", "sex", "age_days",
        "genotype", "temperature_C", "lighting",
    ]

    def _run(self, age_days="5", temperature="25"):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.csv"
            table = directory / "aggregated.csv"
            manifest = directory / "manifest.json"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.fields)
                writer.writeheader()
                for fly in range(4):
                    for time in [0, 6, 12, 18]:
                        writer.writerow({
                            "biological_replicate_id": f"fly{fly}",
                            "time_hours": time,
                            "value": 1.0,
                            "experimental_unit": "fly",
                            "gene_symbol": "para",
                            "cell_type": "s-LNv",
                            "background": "w1118",
                            "batch_id": "batch1",
                            "sex": "female",
                            "age_days": age_days,
                            "genotype": "pdf-GAL4/UAS-GCaMP",
                            "temperature_C": temperature,
                            "lighting": "LD 12:12",
                        })
            return prepare(source, table, manifest)

    def test_non_numeric_age_stage_is_invalid_not_formally_ready(self):
        result = self._run(age_days="adult")
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("invalid_formal_covariates", result["blocking_reasons"])
        self.assertEqual(result["invalid_covariate_counts"]["age_days"], 16)

    def test_non_numeric_temperature_is_invalid_not_formally_ready(self):
        result = self._run(temperature="room_temperature")
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("invalid_formal_covariates", result["blocking_reasons"])
        self.assertEqual(result["invalid_covariate_counts"]["temperature_C"], 16)

    def test_numeric_age_and_temperature_remain_ready(self):
        result = self._run()
        self.assertEqual(result["status"], "ready_for_mixed_model")
        self.assertEqual(result["invalid_covariate_counts"], {})


if __name__ == "__main__":
    unittest.main()
