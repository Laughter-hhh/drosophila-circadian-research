import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_pharmacology_plan import validate


FIELDS = [
    "plan_id", "candidate", "neuron", "readout", "blocker", "concentration",
    "concentration_unit", "application", "vehicle", "washout",
    "blocker_selectivity_source", "concentration_source", "positive_control",
    "negative_control", "off_target_risk", "stage", "source_url",
    "selectivity_status", "dose_response_status", "washout_status",
]


class PharmacologyStageGateTests(unittest.TestCase):
    def _validate(self, selectivity: str, dose: str, washout: str):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "plan_id": "formal-Shaw", "candidate": "Shaw", "neuron": "l-LNv",
            "concentration": "300", "concentration_unit": "nM", "stage": "formal",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/31612994/",
            "selectivity_status": selectivity, "dose_response_status": dose,
            "washout_status": washout,
        })
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        path = Path(handle.name)
        try:
            return validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_formal_plan_rejects_unverified_native_selectivity(self):
        result = self._validate("heterologous_only", "validated", "validated")
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertTrue(any(issue.get("type") == "formal_requires_native_selectivity" for issue in result["issues"]))

    def test_formal_plan_passes_only_after_all_gates(self):
        result = self._validate("native_verified", "validated", "validated")
        self.assertEqual(result["status"], "verified_pharmacology_plan")


if __name__ == "__main__":
    unittest.main()
