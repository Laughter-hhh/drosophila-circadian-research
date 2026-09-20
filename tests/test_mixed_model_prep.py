import csv
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_mixed_model_input import prepare


class MixedModelPreparationTests(unittest.TestCase):
    fields = [
        "biological_replicate_id", "subunit_id", "time_hours", "value", "experimental_unit",
        "gene_symbol", "cell_type", "background", "batch_id", "sex", "age_days",
        "genotype", "temperature_C", "lighting",
    ]

    def _write(self, n_flies=4, missing_covariate=False, conflicting_batch=False, unit="fly"):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=self.fields)
        writer.writeheader()
        for fly_index in range(n_flies):
            for time in [0.0, 6.0, 12.0, 18.0]:
                for cell_index in range(2):
                    writer.writerow({
                        "biological_replicate_id": f"fly{fly_index}",
                        "subunit_id": f"fly{fly_index}_cell{cell_index}",
                        "time_hours": time,
                        "value": 5.0 + 2.0 * math.cos(2.0 * math.pi * time / 24.0) + cell_index * 0.1,
                        "experimental_unit": unit,
                        "gene_symbol": "na",
                        "cell_type": "s-LNv",
                        "background": "w1118",
                        "batch_id": "batch2" if conflicting_batch and cell_index else "batch1",
                        "sex": "female",
                        "age_days": "5",
                        "genotype": "pdf-GAL4/UAS-GCaMP",
                        "temperature_C": "25" if not missing_covariate else "unknown",
                        "lighting": "LD 12:12",
                    })
        handle.close()
        return Path(handle.name)

    def _outputs(self):
        table = Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name)
        manifest = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        return table, manifest

    def test_complete_nested_input_is_ready_for_mixed_model(self):
        source = self._write()
        table, manifest = self._outputs()
        try:
            result = prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
        self.assertEqual(result["status"], "ready_for_mixed_model")
        self.assertEqual(result["n_raw_observations"], 32)
        self.assertEqual(result["n_aggregated_unit_time_means"], 16)
        self.assertEqual(result["n_biological_replicates"], 4)
        self.assertEqual(result["model_specification"]["random_effects"], ["1 | biological_replicate_id"])

    def test_missing_covariate_blocks_formal_handoff(self):
        source = self._write(missing_covariate=True)
        table, manifest = self._outputs()
        try:
            result = prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("missing_formal_covariates", result["blocking_reasons"])
        self.assertIn("temperature_C", result["missing_covariate_counts"])

    def test_metadata_conflict_blocks_formal_handoff(self):
        source = self._write(conflicting_batch=True)
        table, manifest = self._outputs()
        try:
            result = prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("metadata_conflict_within_biological_unit_time", result["blocking_reasons"])

    def test_technical_unit_blocks_formal_handoff(self):
        source = self._write(unit="technical_replicate")
        table, manifest = self._outputs()
        try:
            result = prepare(source, table, manifest)
        finally:
            source.unlink(missing_ok=True)
            table.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertIn("technical_replicate_is_not_biological_unit", result["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
