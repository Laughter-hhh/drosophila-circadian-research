import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_pharmacology_bundle import validate
from scripts.validate_pharmacology_plan import REQUIRED as PLAN_REQUIRED
from scripts.validate_pharmacology_source_log import REQUIRED as SOURCE_REQUIRED


class PharmacologyBundleTests(unittest.TestCase):
    def _public_plan(self):
        return ROOT / "validation" / "public-data" / "primary-pharmacology-methods.csv"

    def _public_source_log(self):
        return ROOT / "validation" / "public-data" / "primary-pharmacology-source-log.csv"

    def _write_pair(self, plan_row, source_row):
        plan_file = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        plan_writer = csv.DictWriter(plan_file, fieldnames=sorted(PLAN_REQUIRED))
        plan_writer.writeheader()
        plan_writer.writerow(plan_row)
        plan_file.close()
        source_file = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        source_writer = csv.DictWriter(source_file, fieldnames=sorted(SOURCE_REQUIRED))
        source_writer.writeheader()
        source_writer.writerow(source_row)
        source_file.close()
        return Path(plan_file.name), Path(source_file.name)

    def _formal_rows(self):
        plan_row = {field: "documented" for field in PLAN_REQUIRED}
        plan_row.update({
            "plan_id": "formal-1", "candidate": "Shaw", "neuron": "l-LNv",
            "readout": "peak K current density", "blocker": "BDS",
            "concentration": "300", "concentration_unit": "nM", "stage": "formal",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/31612994/",
            "selectivity_status": "native_verified", "dose_response_status": "validated",
            "washout_status": "validated",
        })
        source_row = {field: "documented" for field in SOURCE_REQUIRED}
        source_row.update({
            "record_id": "formal-src-1", "plan_id": "formal-1", "candidate": "Shaw", "blocker": "BDS",
            "source_id": "PMID:31612994", "source_url_or_identifier": "https://pubmed.ncbi.nlm.nih.gov/31612994/",
            "source_type": "primary_paper", "organism": "Drosophila melanogaster", "target_neuron": "l-LNv",
            "assay": "whole-cell electrophysiology; pharmacological blocker",
            "readout_match": "membrane_potential_or_current", "evidence_label": "near_direct",
            "claim_type": "conclusion", "source_support_status": "checked",
            "concentration_status": "matched", "reported_concentration": "300",
            "reported_concentration_unit": "nM", "selectivity_support_status": "native_verified",
            "result_summary": "Exact starting concentration and native selectivity were independently checked.",
            "decision": "include", "decision_reason": "Formal gate test fixture.",
        })
        return plan_row, source_row

    def test_public_conditional_bundle_is_verified_but_not_formal(self):
        result = validate(self._public_plan(), self._public_source_log())
        self.assertEqual(result["status"], "verified_pharmacology_bundle")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertEqual(result["blocker_provenance"]["status"], "verified_blocker_source_linkage")
        self.assertTrue(any(warning["type"] == "dose_response_not_validated" for warning in result["warnings"]))
        self.assertTrue(any(warning["type"] == "washout_not_validated" for warning in result["warnings"]))

    def test_bundle_requires_blocker_source_log(self):
        result = validate(self._public_plan())
        self.assertEqual(result["status"], "invalid_pharmacology_bundle")
        self.assertTrue(any(issue["type"] == "pharmacology_source_log_required" for issue in result["issues"]))

    def test_missing_plan_blocker_record_is_rejected(self):
        with self._public_source_log().open(newline="", encoding="utf-8") as handle:
            source_rows = list(csv.DictReader(handle))[:-1]
        temp = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(temp, fieldnames=sorted(SOURCE_REQUIRED))
        writer.writeheader()
        writer.writerows(source_rows)
        temp.close()
        source_path = Path(temp.name)
        try:
            result = validate(self._public_plan(), source_path)
        finally:
            source_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_bundle")
        self.assertTrue(any(issue["type"] == "blocker_missing_from_source_log" for issue in result["issues"]))

    def test_formal_bundle_requires_matched_concentration_and_native_selectivity(self):
        plan_row, source_row = self._formal_rows()
        plan_path, source_path = self._write_pair(plan_row, source_row)
        try:
            result = validate(plan_path, source_path)
        finally:
            plan_path.unlink(missing_ok=True)
            source_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_bundle")
        self.assertEqual(result["formal_status"], "formal_gate_passed_external_checks_pending")
        self.assertEqual(result["blocker_provenance"]["status"], "verified_blocker_source_linkage")

    def test_pubmed_url_and_pmid_identifier_are_equivalent(self):
        plan_row, source_row = self._formal_rows()
        source_row["source_url_or_identifier"] = "PMID:31612994"
        plan_path, source_path = self._write_pair(plan_row, source_row)
        try:
            result = validate(plan_path, source_path)
        finally:
            plan_path.unlink(missing_ok=True)
            source_path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_bundle")
        self.assertTrue(result["blocker_provenance"]["records"][0]["source_linked"])


if __name__ == "__main__":
    unittest.main()
