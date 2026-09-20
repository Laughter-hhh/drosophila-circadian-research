import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.fit_fixed_effects_cosinor import fit
from scripts.validate_fixed_effects_result import validate


class FixedEffectsProvenanceTests(unittest.TestCase):
    table = ROOT / "validation" / "synthetic" / "one_timepoint_per_fly_formal_aggregated.csv"
    manifest = ROOT / "validation" / "synthetic" / "one_timepoint_per_fly_formal_manifest.json"

    def test_table_hash_mismatch_blocks_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            table = directory / "aggregated.csv"
            manifest = directory / "manifest.json"
            shutil.copy2(self.table, table)
            shutil.copy2(self.manifest, manifest)
            table.write_text(table.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            result = fit(table, manifest)
            self.assertEqual(result["status"], "blocked_fixed_effects_input")
            self.assertIn("manifest_output_table_hash_mismatch", result["blocking_reasons"])

    def test_result_validator_requires_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            result_path = directory / "result.json"
            result = fit(self.table, self.manifest, result_path)
            self.assertEqual(result["status"], "executed_fixed_effects")
            stripped = json.loads(result_path.read_text(encoding="utf-8"))
            stripped.pop("provenance")
            verdict = validate(stripped)
            self.assertEqual(verdict["status"], "blocked_fixed_effects_result")
            self.assertIn("provenance_hash_match_missing_or_false", verdict["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
