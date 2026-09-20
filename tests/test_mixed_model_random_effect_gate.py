import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.emit_mixed_model_templates import emit


class MixedModelRandomEffectGateTests(unittest.TestCase):
    def _manifest(self, random_effects):
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        path.write_text(
            json.dumps(
                {
                    "status": "ready_for_mixed_model",
                    "model_specification": {"random_effects": random_effects},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_one_timepoint_units_cannot_emit_random_intercept_template(self):
        manifest = self._manifest([])
        output_dir = Path(tempfile.mkdtemp())
        try:
            with self.assertRaisesRegex(ValueError, "does not contain an estimable"):
                emit(manifest, output_dir)
            self.assertEqual(list(output_dir.iterdir()), [])
        finally:
            manifest.unlink(missing_ok=True)
            output_dir.rmdir()

    def test_r_template_checks_packages_before_loading_manifest(self):
        from scripts.emit_mixed_model_templates import R_TEMPLATE

        self.assertLess(R_TEMPLATE.index("requireNamespace"), R_TEMPLATE.index("fromJSON"))


if __name__ == "__main__":
    unittest.main()
