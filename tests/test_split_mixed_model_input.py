import csv
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.split_mixed_model_input import split


class MixedModelStratumSplitTests(unittest.TestCase):
    fields = ["gene_symbol", "cell_type", "background", "biological_replicate_id", "time_hours", "value"]

    def _write(self, rows):
        path = Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_split_preserves_rows_and_has_deterministic_traceability(self):
        source = self._write([
            {"gene_symbol": "para", "cell_type": "s-LNv", "background": "w1118", "biological_replicate_id": "fly1", "time_hours": "0", "value": "1"},
            {"gene_symbol": "Sh", "cell_type": "s-LNv", "background": "w1118", "biological_replicate_id": "fly1", "time_hours": "0", "value": "2"},
            {"gene_symbol": "para", "cell_type": "s-LNv", "background": "w1118", "biological_replicate_id": "fly2", "time_hours": "6", "value": "3"},
        ])
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            result = split(source, directory / "strata", directory / "split-manifest.json")
            manifest = json.loads((directory / "split-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "split_ready")
            self.assertEqual(result["n_analysis_strata"], 2)
            self.assertEqual(result["row_conservation"], {"input_rows": 3, "output_rows": 3, "exact": True})
            self.assertEqual(manifest["strata"], result["strata"])
            self.assertEqual(sum(int(item["n_rows"]) for item in result["strata"]), 3)
            self.assertEqual(len({item["output_file"] for item in result["strata"]}), 2)
            for item in result["strata"]:
                self.assertEqual(len(item["sha256"]), 64)
                self.assertTrue(Path(item["output_file"]).exists())
        source.unlink(missing_ok=True)

    def test_slug_collisions_still_produce_unique_files(self):
        source = self._write([
            {"gene_symbol": "a/b", "cell_type": "s-LNv", "background": "w1118", "biological_replicate_id": "fly1", "time_hours": "0", "value": "1"},
            {"gene_symbol": "a b", "cell_type": "s-LNv", "background": "w1118", "biological_replicate_id": "fly2", "time_hours": "0", "value": "2"},
        ])
        with tempfile.TemporaryDirectory() as directory:
            result = split(source, Path(directory) / "strata", Path(directory) / "manifest.json")
            names = [Path(item["output_file"]).name for item in result["strata"]]
            self.assertEqual(len(names), len(set(names)))
        source.unlink(missing_ok=True)

    def test_missing_stratum_column_is_rejected(self):
        source = Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name)
        source.write_text("gene_symbol,cell_type,value\npara,s-LNv,1\n", encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                split(source, source.parent / "strata", source.parent / "manifest.json")
        finally:
            source.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
