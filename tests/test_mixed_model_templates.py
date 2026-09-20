import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.emit_mixed_model_templates import emit


class MixedModelTemplateTests(unittest.TestCase):
    def _manifest(self, status="ready_for_mixed_model", random_effects=None):
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        if random_effects is None:
            random_effects = ["1 | biological_replicate_id"]
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "blocking_reasons": ["missing_formal_covariates"],
                    "model_specification": {"random_effects": random_effects},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_ready_manifest_emits_three_runtime_templates(self):
        manifest = self._manifest()
        output_dir = Path(tempfile.mkdtemp())
        try:
            result = emit(manifest, output_dir)
            self.assertEqual(result["status"], "templates_emitted")
            self.assertTrue((output_dir / "fit_mixed_model_statsmodels.py").exists())
            self.assertTrue((output_dir / "fit_mixed_model.R").exists())
            self.assertTrue((output_dir / "fit_mixed_model.m").exists())
            self.assertIn("biological_replicate_id", (output_dir / "fit_mixed_model_statsmodels.py").read_text(encoding="utf-8"))
            self.assertIn("fitlme", (output_dir / "fit_mixed_model.m").read_text(encoding="utf-8"))
        finally:
            manifest.unlink(missing_ok=True)
            for path in output_dir.glob("*"):
                path.unlink(missing_ok=True)
            output_dir.rmdir()

    def test_blocked_manifest_cannot_emit_formal_templates(self):
        manifest = self._manifest(status="blocked_mixed_model_input")
        output_dir = Path(tempfile.mkdtemp())
        try:
            with self.assertRaisesRegex(ValueError, "not ready_for_mixed_model"):
                emit(manifest, output_dir)
        finally:
            manifest.unlink(missing_ok=True)
            output_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
