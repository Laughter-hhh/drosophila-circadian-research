import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fit_fixed_effects_cosinor import fit
from scripts.validate_fixed_effects_result import validate


class FixedEffectsZeroAmplitudeTests(unittest.TestCase):
    table = ROOT / "validation" / "synthetic" / "one_timepoint_flat_formal_aggregated.csv"
    manifest = ROOT / "validation" / "synthetic" / "one_timepoint_flat_formal_manifest.json"

    def test_flat_signal_has_near_zero_amplitude_and_undefined_phase(self):
        result = fit(self.table, self.manifest)
        self.assertEqual(result["status"], "executed_fixed_effects")
        self.assertLess(result["cosinor"]["amplitude"], 1e-10)
        self.assertIsNone(result["cosinor"]["acrophase_hours"])
        self.assertEqual(validate(result)["status"], "verified_fixed_effects_result")


if __name__ == "__main__":
    unittest.main()
