import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_integrated_cross_plan import REQUIRED, validate


FIELDS = sorted(REQUIRED)


class IntegratedCrossPlanTests(unittest.TestCase):
    def _write(self, row, fields=FIELDS):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _row(self, stage="formal", candidate="Shaw"):
        return {
            "cross_id": "integrated-01", "candidate": candidate, "stage": stage,
            "purpose": "adult-restricted RNAi feasibility", "virgin_parent_sex": "female",
            "virgin_parent_genotype": "Pdf-GAL4 genotype", "virgin_parent_stock": "Pdf-GAL4",
            "other_parent_sex": "male", "other_parent_genotype": "Shaw RNAi genotype",
            "other_parent_stock": "Shaw-RNAi", "f1_target_genotype": "Pdf-GAL4/+; UAS-RNAi/+",
            "balancer_or_selection": "markers documented", "reciprocal_cross": "planned",
            "background_control": "driver-only and effector-only siblings", "temperature_C": "18",
            "LD_schedule": "12:12 LD", "timeline_days": "14",
            "stock_source_urls": "https://flybase.org/reports/FBst0080939; https://flybase.org/reports/FBal0239483",
            "driver_stock_candidate": "Pdf-GAL4", "effector_stock_candidate": "Shaw-RNAi",
            "driver_identity_status": "identity_verified", "effector_identity_status": "identity_verified",
            "driver_expression_status": "verified", "adult_restriction_strategy": "verified",
            "developmental_control": "present", "background_match_status": "matched",
            "notes": "synthetic integrated test row",
        }

    def _stock_audit(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["candidate", "verification_status"])
        writer.writeheader()
        writer.writerow({"candidate": "Pdf-GAL4", "verification_status": "identity_verified"})
        writer.writerow({"candidate": "Shaw-RNAi", "verification_status": "identity_verified"})
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

    def test_formal_passes_when_parent_links_and_stock_audit_pass(self):
        cross = self._write(self._row())
        audit = self._stock_audit()
        access = self._source_access()
        try:
            result = validate(cross, audit, access)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
            access.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_integrated_cross_plan")
        self.assertEqual(result["formal_status"], "formal_gate_passed_external_checks_pending")
        self.assertEqual(result["formal_passes"], 1)
        self.assertEqual(result["source_access_report"]["status"], "verified_source_access")

    def test_formal_rejects_effector_not_in_parent_stock_fields(self):
        row = self._row()
        row["other_parent_stock"] = "Wrong-RNAi"
        cross = self._write(row)
        audit = self._stock_audit()
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_integrated_cross_plan")
        self.assertEqual(result["formal_status"], "blocked_by_validation_issues")
        self.assertTrue(any(issue.get("type") == "parent_stock_link_missing" for issue in result["issues"]))

    def test_conditional_pilot_is_explicitly_not_formal_ready(self):
        cross = self._write(self._row("conditional_pilot"))
        audit = self._stock_audit()
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_integrated_cross_plan")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertEqual(result["formal_passes"], 0)

    def test_real_top4_conditional_file_has_only_expected_warnings(self):
        cross = ROOT / "validation" / "public-data" / "top4-rnai-integrated-cross-plan.csv"
        audit = ROOT / "validation" / "public-data" / "shaw-clock-tool-stock-audit.csv"
        result = validate(cross, audit)
        self.assertEqual(result["status"], "verified_integrated_cross_plan")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")
        self.assertEqual(result["n_rows"], 4)
        self.assertEqual(result["formal_passes"], 0)
        self.assertEqual(sum(warning.get("type") == "blocked_for_formal" for warning in result["warnings"]), 4)


    def test_formal_requires_online_source_report(self):
        cross = self._write(self._row())
        audit = self._stock_audit()
        try:
            result = validate(cross, audit)
        finally:
            cross.unlink(missing_ok=True)
            audit.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_integrated_cross_plan")
        self.assertTrue(any(issue.get("type") == "formal_requires_online_source_access" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()






