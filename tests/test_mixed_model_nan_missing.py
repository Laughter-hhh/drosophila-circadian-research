import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_mixed_model_input import prepare


class MixedModelNanMissingTests(unittest.TestCase):
    fields = [
        "biological_replicate_id", "time_hours", "value", "experimental_unit",
        "batch_id", "sex", "age_days", "genotype", "temperature_C", "lighting",
    ]

    def _write(self, temperature="25", value="1.0", time="0"):
        source = Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name)
        with source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            for fly in range(4):
                writer.writerow({
                    "biological_replicate_id": f"fly{fly}", "time_hours": time, "value": value,
                    "experimental_unit": "fly", "batch_id": "b1", "sex": "female",
                    "age_days": "5", "genotype": "control", "temperature_C": temperature, "lighting": "LD",
                })
        return source

    def _outputs(self):
        return (Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name), Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name))

    def test_nan_covariate_is_counted_as_missing(self):
        source = self._write(temperature="nan")
        table, manifest = self._outputs()
        try:
            result = prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("missing_formal_covariates", result["blocking_reasons"])
        self.assertEqual(result["missing_covariate_counts"]["temperature_C"], 4)

    def test_nonfinite_value_is_rejected(self):
        source = self._write(value="nan")
        table, manifest = self._outputs()
        try:
            with self.assertRaisesRegex(ValueError, "invalid row"):
                prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)

    def test_nonfinite_time_is_rejected(self):
        source = self._write(time="nan")
        table, manifest = self._outputs()
        try:
            with self.assertRaisesRegex(ValueError, "invalid row"):
                prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
