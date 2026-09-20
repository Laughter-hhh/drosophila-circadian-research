import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_genetic_stage_gate import REQUIRED, validate


FIELDS = sorted(REQUIRED)


class GeneticStageGateTests(unittest.TestCase):
    def _write(self, row, fields=FIELDS):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _row(self, stage="conditional_pilot", candidate="Shaw"):
        return {
            "cross_id": "gate-01", "candidate": candidate, "stage": stage,
            "driver_stock_candidate": "Pdf-GAL4", "effector_stock_candidate": "Shaw-RNAi",
            "driver_identity_status": "identity_verified", "effector_identity_status": "identity_verified",
            "driver_expression_status": "verified", "adult_restriction_strategy": "verified",
            "developmental_control": "present", "background_match_status": "matched",
            "source_urls": "https://flybase.org/reports/FBst0080939; https://flybase.org/reports/FBal0239483",
            "notes": "synthetic test row",
        }

    def _stock_audit(self, driver_status="identity_verified", effector_status="identity_verified"):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["candidate", "verification_status"])
        writer.writeheader()
        writer.writerow({"candidate": "Pdf-GAL4", "verification_status": driver_status})
        writer.writerow({"candidate": "Shaw-RNAi", "verification_status": effector_status})
        handle.close()
        return Path(handle.name)


    def _source_access(self, driver_status="reachable_content_verified", effector_status="reachable_content_verified", top_status="verified_source_access"):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({
            "status": top_status,
            "records": [
                {
                    "record_id": "Pdf-GAL4",
                    "source_url": "https://flybase.org/reports/FBst0080939",
                    "access_status": driver_status,
                    "verification_method": "browser_manual",
                    "checked_at_utc": "2026-09-08T10:00:00+00:00",
                    "observed_tokens": ["FBst0080939", "80939"],
                    "observation_note": "Browser view showed the stock identifier and listed genotype.",
                },
                {
                    "record_id": "Shaw-RNAi",
                    "source_url": "https://flybase.org/reports/FBal0239483",
                    "access_status": effector_status,
                    "verification_method": "browser_manual",
                    "checked_at_utc": "2026-09-08T10:00:00+00:00",
                    "observed_tokens": ["FBal0239483"],
                    "observation_note": "Browser view showed the reagent identifier.",
                },
            ],
        }, handle)
        handle.close()
        return Path(handle.name)

    def test_formal_passes_only_when_stock_join_and_gates_pass(self):
        cross = self._write(self._row("formal"))
        audit = self._stock_audit()
        access = self._source_access()
        try:
            result = validate(cross, audit, access)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
            access.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_genetic_stage_gate")
        self.assertEqual(result["formal_passes"], 1)
        self.assertEqual(result["formal_status"], "formal_gate_passed_external_checks_pending")

    def test_formal_requires_stock_audit_file(self):
        cross = self._write(self._row("formal"))
        try:
            result = validate(cross)
        finally:
            cross.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "formal_requires_stock_audit" for issue in result["issues"]))

    def test_partial_stock_blocks_formal_but_allows_conditional_pilot(self):
        cross = self._write(self._row("formal"))
        audit = self._stock_audit(effector_status="partial")
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "formal_requires_audited_stock_identity" for issue in result["issues"]))

        row = self._row("conditional_pilot")
        cross = self._write(row)
        try:
            pilot = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(pilot["status"], "verified_genetic_stage_gate")
        self.assertEqual(pilot["formal_status"], "conditional_pilot_only")
        self.assertTrue(any(warning.get("type") == "blocked_for_formal" for warning in pilot["warnings"]))

    def test_declared_identity_cannot_exceed_audit(self):
        cross = self._write(self._row("conditional_pilot"))
        audit = self._stock_audit(driver_status="partial")
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertTrue(any(warning.get("type") == "declared_status_exceeds_audit" for warning in result["warnings"]))

    def test_na_gene_symbol_is_not_treated_as_missing(self):
        cross = self._write(self._row("conditional_pilot", candidate="na"))
        try:
            result = validate(cross)
        finally:
            cross.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertFalse(any(issue.get("field") == "candidate" for issue in result["issues"]))


    def test_formal_requires_online_source_report(self):
        cross = self._write(self._row("formal"))
        audit = self._stock_audit()
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_genetic_stage_gate")
        self.assertTrue(any(issue.get("type") == "formal_requires_online_source_access" for issue in result["issues"]))

    def test_conditional_pilot_warns_when_online_content_is_unverified(self):
        cross = self._write(self._row("conditional_pilot"))
        audit = self._stock_audit()
        access = self._source_access("reachable_content_unverified", "reachable_content_unverified", "conditional_source_access")
        try:
            result = validate(cross, audit, access)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
            access.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertTrue(any(warning.get("type") == "online_source_not_verified" for warning in result["warnings"]))


    def test_formal_rejects_unverified_online_content(self):
        cross = self._write(self._row("formal"))
        audit = self._stock_audit()
        access = self._source_access("reachable_content_unverified", "reachable_content_unverified", "conditional_source_access")
        try:
            result = validate(cross, audit, access)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
            access.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_genetic_stage_gate")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "formal_requires_verified_online_source_access" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()






