import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_experiment_plan import REQUIRED, validate


class ExperimentPlanTests(unittest.TestCase):
    def _write(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _base(self):
        return {
            "plan_id": "EXP-01", "candidate": "Shaw", "module": "channel_screen",
            "hypothesis": "Shaw conductance contributes to l-LNv membrane potential rhythm.",
            "causal_link": "channel activity -> l-LNv membrane potential",
            "target_neuron": "l-LNv", "species": "Drosophila melanogaster",
            "stage": "conditional_pilot", "perturbation": "pharmacology",
            "time_basis": "ZT0, ZT6, ZT12, ZT18", "lighting_condition": "LD 12:12 then DD",
            "sex_age_temperature": "female, 5-7 days, 25 C",
            "experimental_unit": "cell", "biological_unit_definition": "one brain per fly; one primary cell per brain",
            "minimum_n": "6", "sample_size_basis": "feasibility variance estimate; not confirmatory power",
            "primary_readout": "whole-cell resting membrane potential and peak K current",
            "secondary_readouts": "access resistance; seal; cell health",
            "controls": "vehicle; driver_only; effector_only; background; time_matched",
            "qc_metrics": "seal; access; series; holding_current; cell_health",
            "analysis_plan": "predefined QC then biological-unit summary by ZT; exploratory effect size and CI",
            "expected_result_matrix": "blocker effect at one phase only vs phase-dependent effect vs no effect",
            "alternative_explanations": "off-target peptide; cell-selection bias; bath application kinetics",
            "go_no_go_rule": "advance only if direction replicates and QC passes in independent preparation",
            "developmental_boundary": "adult_restricted", "reagent_identity_status": "pending_audit",
            "stock_identity_status": "not_applicable", "source_status": "planning",
        }

    def test_conditional_channel_pilot_passes_with_explicit_boundaries(self):
        path = self._write([self._base()])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_experiment_plan")
        self.assertEqual(result["formal_status"], "conditional_pilot_only")

    def test_formal_requires_verified_reagent(self):
        row = self._base()
        row.update({"stage": "formal_experiment", "stock_identity_status": "verified"})
        path = self._write([row])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_experiment_plan")
        self.assertTrue(any(issue["type"] == "formal_requires_verified_reagent_or_na" for issue in result["issues"]))

    def test_external_optogenetic_plan_requires_light_and_retinal_controls(self):
        row = self._base()
        row.update({
            "plan_id": "EXP-02", "module": "external_input", "perturbation": "optogenetics",
            "controls": "driver_only; effector_only; background; time_matched",
            "reagent_identity_status": "verified", "stock_identity_status": "verified",
        })
        path = self._write([row])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_experiment_plan")
        self.assertTrue(any(warning["type"] == "external_input_requires_light_control" for warning in result["warnings"]))
        self.assertTrue(any(warning["type"] == "optogenetics_requires_retinal_control" for warning in result["warnings"]))

    def test_formal_external_input_missing_controls_is_blocked(self):
        row = self._base()
        row.update({
            "plan_id": "EXP-03", "module": "external_input", "perturbation": "optogenetics",
            "stage": "formal_experiment", "reagent_identity_status": "verified", "stock_identity_status": "verified",
            "controls": "driver_only; effector_only; background; time_matched",
        })
        path = self._write([row])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_experiment_plan")
        self.assertTrue(any(issue["type"] == "external_input_requires_light_control" for issue in result["issues"]))

    def test_time_system_is_required(self):
        row = self._base()
        row["time_basis"] = "phase 1-4"
        path = self._write([row])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_experiment_plan")
        self.assertTrue(any(issue["type"] == "time_basis_must_declare_ZT_or_CT" for issue in result["issues"]))

    def test_simple_two_group_power_cannot_back_a_mixed_effects_analysis(self):
        row = self._base()
        row.update({
            "stage": "formal_experiment", "experimental_unit": "fly", "minimum_n": "50",
            "reagent_identity_status": "verified", "stock_identity_status": "verified",
            "analysis_plan": "mixed-effects model with fly random intercept and prespecified contrasts",
        })
        plan = self._write([row])
        power_payload = {
            "report_id": "TEST-SIMPLE-POWER",
            "records": [{
                "plan_id": "EXP-01", "design_type": "two_group_mean_equal_n",
                "independent_biological_unit": "fly", "effect_size_metric": "cohens_d",
                "effect_size": 0.8, "effect_size_low": 0.8, "effect_size_high": 0.8,
                "alpha": 0.05, "target_power": 0.8, "comparison_count": 1,
                "multiplicity_method": "none", "cluster_structure": "one fly per unit",
                "basis_status": "pilot_estimate", "basis_source": "synthetic fixture",
                "calculation_method": "normal_approximation_two_group_equal_n",
                "n_per_group": 25, "minimum_n_total": 50,
            }],
        }
        power_handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(power_payload, power_handle)
        power_handle.close()
        try:
            result = validate(plan, Path(power_handle.name))
        finally:
            plan.unlink(missing_ok=True)
            Path(power_handle.name).unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_experiment_plan")
        self.assertTrue(any(issue["type"] == "power_design_mismatch_complex_analysis" for issue in result["issues"]))

    def test_public_synthetic_plan_is_verified_with_power_gate(self):
        plan = ROOT / "validation" / "public-data" / "synthetic-experiment-plan.csv"
        power = ROOT / "validation" / "public-data" / "synthetic-power-basis.json"
        result = validate(plan, power)
        self.assertEqual(result["status"], "verified_experiment_plan")
        self.assertEqual(result["n_rows"], 4)
        self.assertEqual(result["formal_rows"], 1)
        self.assertEqual(result["formal_passes"], 1)
        self.assertEqual(result["power_gate"]["status"], "verified_power_basis_report")

    def test_formal_plan_without_power_basis_is_blocked(self):
        row = self._base()
        row.update({
            "stage": "formal_experiment",
            "reagent_identity_status": "verified",
            "stock_identity_status": "verified",
        })
        path = self._write([row])
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_experiment_plan")
        self.assertTrue(any(issue["type"] == "formal_requires_power_basis_report" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()




