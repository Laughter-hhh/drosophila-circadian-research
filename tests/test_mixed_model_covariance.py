import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MixedModelCovarianceTests(unittest.TestCase):
    template_path = ROOT / "validation" / "synthetic" / "mixed_model_templates" / "fit_mixed_model_statsmodels.py"

    def test_amplitude_interval_uses_cross_covariance(self):
        text = self.template_path.read_text(encoding="utf-8")
        self.assertIn("cov_params", text)
        self.assertIn("cov_cos_sin", text)
        self.assertIn("2.0 * beta_cos * beta_sin * cov_cos_sin", text)


if __name__ == "__main__":
    unittest.main()
