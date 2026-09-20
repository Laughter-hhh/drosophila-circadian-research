import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fit_fixed_effects_cosinor import fit


class FixedEffectsCosinorTests(unittest.TestCase):
    one_timepoint_table = ROOT / "validation" / "synthetic" / "one_timepoint_per_fly_formal_aggregated.csv"
    one_timepoint_manifest = ROOT / "validation" / "synthetic" / "one_timepoint_per_fly_formal_manifest.json"
    repeated_table = ROOT / "validation" / "synthetic" / "nested_clock_data_formal_aggregated.csv"
    repeated_manifest = ROOT / "validation" / "synthetic" / "nested_clock_data_formal_manifest.json"

    def test_one_timepoint_fixture_executes_with_hc3_qc(self):
        result = fit(self.one_timepoint_table, self.one_timepoint_manifest)
        self.assertEqual(result["status"], "executed_fixed_effects")
        self.assertEqual(result["n_repeated_biological_replicates"], 0)
        self.assertAlmostEqual(result["cosinor"]["amplitude"], 4.0, places=8)
        self.assertTrue(result["technical_qc"]["full_rank"])

    def test_repeated_fixture_is_not_accepted_by_fixed_effects_branch(self):
        result = fit(self.repeated_table, self.repeated_manifest)
        self.assertEqual(result["status"], "blocked_fixed_effects_wrong_design")


if __name__ == "__main__":
    unittest.main()
