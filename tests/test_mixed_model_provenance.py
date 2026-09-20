import csv
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.prepare_mixed_model_input import prepare
from scripts.split_mixed_model_input import split


class MixedModelProvenanceTests(unittest.TestCase):
    fields = [
        "gene_symbol", "cell_type", "background", "biological_replicate_id",
        "time_hours", "value", "experimental_unit", "batch_id", "sex", "age_days",
        "genotype", "temperature_C", "lighting",
    ]

    def _write(self, path: Path):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            for fly in range(4):
                for time in [0, 6, 12, 18]:
                    writer.writerow({
                        "gene_symbol": "para",
                        "cell_type": "s-LNv",
                        "background": "w1118",
                        "biological_replicate_id": f"fly{fly}",
                        "time_hours": time,
                        "value": 1.0,
                        "experimental_unit": "fly",
                        "batch_id": "batch1",
                        "sex": "female",
                        "age_days": "5",
                        "genotype": "pdf-GAL4/UAS-GCaMP",
                        "temperature_C": "25",
                        "lighting": "LD 12:12",
                    })

    def test_prepare_manifest_records_input_and_output_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.csv"
            self._write(source)
            result = prepare(source, directory / "aggregated.csv", directory / "manifest.json")
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "ready_for_mixed_model")
            for key in ["input_file_metadata", "output_table_metadata"]:
                metadata = manifest[key]
                self.assertEqual(metadata["size_bytes"], Path(metadata["path"]).stat().st_size)
                self.assertEqual(len(metadata["sha256"]), 64)
            self.assertEqual(manifest["input_file_metadata"]["sha256"], result["input_file_metadata"]["sha256"])

    def test_split_manifest_records_input_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.csv"
            self._write(source)
            result = split(source, directory / "strata", directory / "split.json")
            manifest = json.loads((directory / "split.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["input_file_metadata"]["sha256"]), 64)
            self.assertEqual(manifest["input_file_metadata"]["sha256"], result["input_file_metadata"]["sha256"])


if __name__ == "__main__":
    unittest.main()
