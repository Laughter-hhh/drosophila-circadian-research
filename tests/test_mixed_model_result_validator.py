import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_mixed_model_result import validate


def valid_result():
    return {
        "status": "executed_mixed_model",
        "formula": "value ~ cos24 + sin24",
        "random_effect": "1 | biological_replicate_id",
        "n_rows": 32,
        "n_biological_replicates": 8,
        "converged": True,
        "fixed_effects": {"cos24": 2.0, "sin24": -1.0},
        "cosinor": {
            "beta_cos24": 2.0,
            "beta_sin24": -1.0,
            "amplitude": 2.236,
            "acrophase_hours": 1.76,
            "amplitude_normal_approx_95_ci": [1.5, 3.0],
        },
        "residual_diagnostics": {"n": 32, "n_finite": 32, "mean": 0.0, "sd": 0.4, "max_abs": 1.1},
        "technical_qc": {"converged": True, "all_residuals_finite": True},
        "runtime_versions": {"python": "3.12", "numpy": "2", "pandas": "2", "statsmodels": "0.14"},
    }


class MixedModelResultValidatorTests(unittest.TestCase):
    def test_complete_result_passes_technical_gate(self):
        verdict = validate(valid_result())
        self.assertEqual(verdict["status"], "verified_mixed_model_result")
        self.assertEqual(verdict["blocking_reasons"], [])

    def test_nonconvergence_blocks_verification(self):
        result = valid_result()
        result["converged"] = False
        verdict = validate(result)
        self.assertEqual(verdict["status"], "blocked_mixed_model_result")
        self.assertIn("model_not_converged", verdict["blocking_reasons"])

    def test_missing_residual_qc_blocks_verification(self):
        result = valid_result()
        result.pop("residual_diagnostics")
        verdict = validate(result)
        self.assertEqual(verdict["status"], "blocked_mixed_model_result")
        self.assertIn("residual_diagnostics_missing", verdict["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
