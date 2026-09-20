import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_pharmacology_source_log import REQUIRED, validate


class PharmacologySourceLogTests(unittest.TestCase):
    def _row(self):
        return {
            "record_id": "SRC-1", "plan_id": "P1", "candidate": "Shaw", "blocker": "BDS",
            "source_id": "PMID:31612994", "source_url_or_identifier": "https://pubmed.ncbi.nlm.nih.gov/31612994/",
            "source_type": "primary_paper", "organism": "Drosophila melanogaster", "target_neuron": "l-LNv",
            "assay": "whole-cell electrophysiology; pharmacological blocker", "readout_match": "membrane_potential_or_current",
            "evidence_label": "near_direct", "claim_type": "conclusion", "source_support_status": "checked",
            "concentration_status": "not_assessed", "reported_concentration": "NA", "reported_concentration_unit": "NA",
            "selectivity_support_status": "not_assessed", "result_summary": "Blocker is a starting condition; native selectivity requires a local audit.",
            "decision": "conditional", "decision_reason": "Use only as a pilot condition.",
        }

    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def test_valid_conditional_source_log(self):
        path = self._write(self._row())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_source_log")

    def test_identifier_reference_is_allowed(self):
        row = self._row()
        row["source_url_or_identifier"] = "PMID:31612994"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_source_log")

    def test_matched_concentration_requires_value_and_unit(self):
        row = self._row()
        row["concentration_status"] = "matched"
        row["reported_concentration"] = "NA"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_source_log")
        self.assertTrue(any(issue["type"] == "matched_concentration_requires_positive_value" for issue in result["issues"]))

    def test_duplicate_plan_candidate_blocker_is_rejected(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        row = self._row()
        writer.writerow(row)
        row["record_id"] = "SRC-2"
        writer.writerow(row)
        handle.close()
        file_path = Path(handle.name)
        try:
            result = validate(file_path)
        finally:
            file_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_source_log")
        self.assertTrue(any(issue["type"] == "duplicate_plan_candidate_blocker" for issue in result["issues"]))

    def test_public_fixture_is_structurally_valid(self):
        path = ROOT / "validation" / "public-data" / "primary-pharmacology-source-log.csv"
        result = validate(path)
        self.assertEqual(result["status"], "verified_pharmacology_source_log")
        self.assertEqual(result["n_records"], 4)


if __name__ == "__main__":
    unittest.main()
