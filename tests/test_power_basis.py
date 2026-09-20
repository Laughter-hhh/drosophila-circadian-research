import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.validate_power_basis import validate_file, validate_payload


class PowerBasisTests(unittest.TestCase):
    def _payload(self):
        return {
            "report_id": "TEST-POWER",
            "records": [{
                "plan_id": "EXP-01",
                "design_type": "two_group_mean_equal_n",
                "independent_biological_unit": "fly",
                "effect_size_metric": "cohens_d",
                "effect_size": 0.8,
                "effect_size_low": 0.5,
                "effect_size_high": 1.0,
                "alpha": 0.05,
                "target_power": 0.8,
                "comparison_count": 1,
                "multiplicity_method": "none",
                "cluster_structure": "one fly contributes one independent unit",
                "basis_status": "pilot_estimate",
                "basis_source": "synthetic fixture",
                "calculation_method": "normal_approximation_two_group_equal_n",
                "n_per_group": 63,
                "minimum_n_total": 126,
            }],
        }

    def test_sensitivity_conservative_two_group_calculation_passes(self):
        result = validate_payload(self._payload())
        self.assertEqual(result["status"], "verified_power_basis_report")
        record = result["records"][0]
        self.assertTrue(record["formal_eligible"])
        self.assertEqual(record["calculation"]["recommended_n_per_group_conservative"], 63)

    def test_underpowered_declared_n_is_blocked(self):
        payload = self._payload()
        payload["records"][0]["n_per_group"] = 24
        payload["records"][0]["minimum_n_total"] = 48
        result = validate_payload(payload)
        self.assertEqual(result["status"], "invalid_power_basis_report")
        self.assertTrue(any(item["type"] == "n_per_group_below_conservative_sensitivity" for item in result["issues"]))

    def test_complex_nested_design_requires_external_method(self):
        payload = self._payload()
        record = payload["records"][0]
        record.update({
            "design_type": "nested_or_cosinor_external",
            "effect_size_metric": "amplitude_difference",
            "calculation_method": "normal_approximation_two_group_equal_n",
        })
        result = validate_payload(payload)
        self.assertEqual(result["status"], "invalid_power_basis_report")
        self.assertTrue(any(item["type"] == "complex_design_requires_external_or_simulation_method" for item in result["issues"]))

    def test_public_fixture_is_verified(self):
        result = validate_file(ROOT / "validation" / "public-data" / "synthetic-power-basis.json")
        self.assertEqual(result["status"], "verified_power_basis_report")
        self.assertEqual(result["n_formal_eligible"], 1)


if __name__ == "__main__":
    unittest.main()
