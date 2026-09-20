import csv
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.prepare_mixed_model_input import prepare


class MixedModelAnalysisStratumGateTests(unittest.TestCase):
    fields = [
        "biological_replicate_id", "time_hours", "value", "experimental_unit",
        "gene_symbol", "cell_type", "background", "batch_id", "sex", "age_days",
        "genotype", "temperature_C", "lighting",
    ]

    def test_multiple_gene_strata_block_and_do_not_create_cross_stratum_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.csv"
            table = directory / "aggregated.csv"
            manifest = directory / "manifest.json"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.fields)
                writer.writeheader()
                for fly in range(4):
                    for gene in ["para", "Sh"]:
                        for time in [0, 6, 12, 18]:
                            writer.writerow({
                                "biological_replicate_id": f"fly{fly}",
                                "time_hours": time,
                                "value": 1.0,
                                "experimental_unit": "fly",
                                "gene_symbol": gene,
                                "cell_type": "s-LNv",
                                "background": "w1118",
                                "batch_id": "batch1",
                                "sex": "female",
                                "age_days": "5",
                                "genotype": "pdf-GAL4/UAS-GCaMP",
                                "temperature_C": "25",
                                "lighting": "LD 12:12",
                            })
            result = prepare(source, table, manifest)

        self.assertEqual(result["status"], "blocked_mixed_model_input")
        self.assertEqual(result["n_analysis_strata"], 2)
        self.assertIn("multiple_analysis_strata_split_input_before_modeling", result["blocking_reasons"])
        self.assertEqual(result["n_repeated_biological_replicates"], 8)
        self.assertEqual(result["model_specification"]["random_effects"], ["1 | biological_replicate_id"])

    def test_single_stratum_keeps_repeated_fly_random_intercept(self):
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
                            "age_days": "5",
                            "genotype": "pdf-GAL4/UAS-GCaMP",
                            "temperature_C": "25",
                            "lighting": "LD 12:12",
                        })
            result = prepare(source, table, manifest)

        self.assertEqual(result["status"], "ready_for_mixed_model")
        self.assertEqual(result["n_analysis_strata"], 1)
        self.assertEqual(result["n_repeated_biological_replicates"], 4)
        self.assertEqual(result["model_specification"]["random_effects"], ["1 | biological_replicate_id"])


if __name__ == "__main__":
    unittest.main()
