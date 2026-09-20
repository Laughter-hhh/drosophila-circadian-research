import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MixedModelPrepCliStatusTests(unittest.TestCase):
    def test_blocked_manifest_returns_nonzero_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "input.csv"
            table = directory / "aggregated.csv"
            manifest = directory / "manifest.json"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["biological_replicate_id", "time_hours", "value", "experimental_unit"])
                writer.writeheader()
                for fly in range(4):
                    for time in [0, 6, 12]:
                        writer.writerow({"biological_replicate_id": f"fly{fly}", "time_hours": time, "value": 1.0, "experimental_unit": "fly"})
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "prepare_mixed_model_input.py"), str(source), "--output-table", str(table), "--output-json", str(manifest)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            result = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked_mixed_model_input")


if __name__ == "__main__":
    unittest.main()
