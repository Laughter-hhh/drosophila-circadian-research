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


class PharmacologyPlanTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _base(self, stage="pilot"):
        row = {field: "documented" for field in FIELDS}
        row.update({
            "plan_id": "P1", "candidate": "Shaw", "neuron": "l-LNv", "readout": "K current density",
            "blocker": "BDS", "concentration": "300", "concentration_unit": "nM",
            "application": "bath perfusion", "vehicle": "saline matched",
            "washout": "5 min washout", "stage": stage,
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/31612994/",
            "selectivity_status": "heterologous_only", "dose_response_status": "not_assessed",
            "washout_status": "needs_confirmation",
        })
        return row

    def _public_evidence(self):
        return (
            ROOT / "validation" / "public-data" / "candidate-evidence-real.csv",
            ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv",
        )

    def _public_mapping(self):
        return ROOT / "validation" / "public-data" / "pharmacology-candidate-synonyms.csv"

    def test_complete_pilot_is_structurally_verified_but_formal_blocked(self):
        path = self._write(self._base("pilot"))
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_plan")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertTrue(any(warning.get("type") == "blocked_for_formal" for warning in result["warnings"]))

    def test_missing_concentration_source_is_rejected(self):
        row = self._base("pilot")
        row["concentration_source"] = "NA"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("field") == "concentration_source" for issue in result["issues"]))

    def test_formal_pass_requires_all_three_pharmacology_gates(self):
        row = self._base("formal")
        row.update({
            "selectivity_status": "native_verified",
            "dose_response_status": "validated",
            "washout_status": "validated",
        })
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_plan")
        self.assertEqual(result["formal_rows"], 1)
        self.assertEqual(result["formal_passes"], 1)
        self.assertEqual(result["formal_status"], "formal_gate_passed_external_checks_pending")

    def test_incomplete_formal_plan_is_blocked(self):
        path = self._write(self._base("formal"))
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "formal_requires_native_selectivity" for issue in result["issues"]))

    def test_unknown_stage_is_rejected_instead_of_silently_verified(self):
        path = self._write(self._base("exploratory_pilot"))
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "invalid_stage" for issue in result["issues"]))

    def test_joint_gate_requires_search_log_when_evidence_table_is_requested(self):
        path = self._write(self._base("pilot"))
        evidence, _ = self._public_evidence()
        try:
            result = validate(path, evidence)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertTrue(any(issue.get("type") == "candidate_evidence_search_log_required" for issue in result["issues"]))

    def test_joint_gate_links_exact_candidate_source_and_label(self):
        path = self._write(self._base("pilot"))
        evidence, log = self._public_evidence()
        try:
            result = validate(path, evidence, log)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_pharmacology_plan")
        self.assertEqual(result["candidate_provenance"]["status"], "verified_candidate_evidence_linkage")
        self.assertEqual(result["candidate_provenance"]["records"][0]["candidate"], "Shaw")

    def test_joint_gate_rejects_candidate_absent_from_evidence_table(self):
        pharm = ROOT / "validation" / "public-data" / "primary-pharmacology-methods.csv"
        evidence, log = self._public_evidence()
        result = validate(pharm, evidence, log)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertTrue(any(issue.get("type") == "candidate_missing_from_evidence_table" and issue.get("candidate") == "Shaker" for issue in result["issues"]))

    def test_checked_synonym_mapping_resolves_name_but_not_evidence_strength(self):
        pharm = ROOT / "validation" / "public-data" / "primary-pharmacology-methods.csv"
        evidence, log = self._public_evidence()
        mapping = self._public_mapping()
        result = validate(pharm, evidence, log, mapping)
        shaker_records = [record for record in result["candidate_provenance"]["records"] if record["candidate"] == "Shaker"]
        self.assertEqual(len(shaker_records), 1)
        self.assertTrue(shaker_records[0]["mapping_used"])
        self.assertEqual(shaker_records[0]["evidence_candidate"], "Sh")
        self.assertFalse(any(issue.get("type") == "candidate_missing_from_evidence_table" and issue.get("candidate") == "Shaker" for issue in result["issues"]))
        self.assertTrue(any(issue.get("type") == "candidate_evidence_label_not_actionable" and issue.get("candidate") == "Shaker" for issue in result["issues"]))

    def test_mapping_cannot_be_used_without_candidate_evidence_table(self):
        path = self._write(self._base("pilot"))
        mapping = self._public_mapping()
        try:
            result = validate(path, candidate_mapping_path=mapping)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_pharmacology_plan")
        self.assertTrue(any(issue.get("type") == "candidate_mapping_requires_evidence_table" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
