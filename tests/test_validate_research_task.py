import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_research_task import validate


class ResearchTaskContractTests(unittest.TestCase):
    def test_template_is_valid(self):
        template = ROOT / "assets" / "research-task-template.json"
        self.assertEqual(validate(template), [])

    def test_executed_task_requires_inputs(self):
        data = {
            "task_id": "x",
            "status": "executed",
            "research_question": "q",
            "species": "Drosophila melanogaster",
            "experimental_unit": "fly",
            "primary_readout": "v",
            "required_metadata": [],
            "expected_outputs": [],
            "acceptance_tests": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(data, handle)
            path = Path(handle.name)
        try:
            errors = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("input_files is required for status=executed", errors)
        self.assertIn("analysis_plan is required for status=executed", errors)


if __name__ == "__main__":
    unittest.main()
