import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MixedModelTemplateRuntimeGateTests(unittest.TestCase):
    template_dir = ROOT / "validation" / "synthetic" / "mixed_model_templates"

    def test_python_template_has_explicit_missing_backend_status(self):
        text = (self.template_dir / "fit_mixed_model_statsmodels.py").read_text(encoding="utf-8")
        self.assertIn("blocked_mixed_model_runtime_unavailable", text)
        self.assertIn("find_spec", text)

    def test_r_and_matlab_templates_have_dependency_guards(self):
        r_text = (self.template_dir / "fit_mixed_model.R").read_text(encoding="utf-8")
        matlab_text = (self.template_dir / "fit_mixed_model.m").read_text(encoding="utf-8")
        self.assertIn("requireNamespace", r_text)
        self.assertIn("fitlme','file'", matlab_text)


if __name__ == "__main__":
    unittest.main()
