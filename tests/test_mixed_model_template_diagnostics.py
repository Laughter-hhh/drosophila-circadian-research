import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MixedModelTemplateDiagnosticsTests(unittest.TestCase):
    template_path = ROOT / "validation" / "synthetic" / "mixed_model_templates" / "fit_mixed_model_statsmodels.py"

    def test_generated_python_template_records_reproducibility_fields(self):
        text = self.template_path.read_text(encoding="utf-8")
        for token in ["converged", "residual_diagnostics", "runtime_versions", "amplitude_normal_approx_95_ci", "result_path"]:
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
