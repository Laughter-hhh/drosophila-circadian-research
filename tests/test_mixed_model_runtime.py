import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_mixed_model_runtime import probe


class MixedModelRuntimeTests(unittest.TestCase):
    def test_probe_is_explicit_about_backend_availability(self):
        result = probe()
        self.assertIn(result["status"], {"runtime_available", "blocked_mixed_model_runtime_unavailable"})
        self.assertIn("statsmodels", result["python_packages"])
        self.assertIn("Rscript", result["executables"])
        self.assertIn("available_backends", result)
        if not result["available_backends"]:
            self.assertEqual(result["status"], "blocked_mixed_model_runtime_unavailable")


if __name__ == "__main__":
    unittest.main()
