import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_information_gain_pilot import validate


FIELDS = [
    "plan_id", "candidate", "missing_fact", "causal_link", "target_neuron", "stage", "perturbation",
    "reagent_identifier", "reagent_identity_status", "stock_identifier", "stock_identity_status", "readout",
    "experimental_unit", "minimum_n", "sample_size_basis", "positive_control", "negative_control",
    "developmental_boundary", "go_no_go_rule", "source_status",
]


class InformationGainPilotTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _valid(self):
        return {
            "plan_id": "IG-001", "candidate": "Shaw", "missing_fact": "Does acute channel perturbation change l-LNv current?",
            "causal_link": "channel activity -> l-LNv membrane current", "target_neuron": "l-LNv",
            "stage": "information_gain_pilot", "perturbation": "pharmacology",
            "reagent_identifier": "not_yet_selected_pending_native_selectivity_audit", "reagent_identity_status": "pending_audit",
            "stock_identifier": "not_applicable", "stock_identity_status": "not_applicable",
            "readout": "whole-cell peak current density and resting membrane potential", "experimental_unit": "cell",
            "minimum_n": "6", "sample_size_basis": "six cells per condition for feasibility and variance estimate; not powered for confirmatory inference",
            "positive_control": "known current isolation control", "negative_control": "vehicle-matched saline",
            "developmental_boundary": "adult_restricted", "go_no_go_rule": "advance only if effect is reproducible and vehicle/off-target QC passes",
            "source_status": "planning",
        }

    def test_valid_pilot_is_verified(self):
        path = self._write(self._valid())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_information_gain_pilot")

    def test_pending_reagent_cannot_use_a_guessed_name(self):
        row = self._valid()
        row["reagent_identifier"] = "DTX"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_information_gain_pilot")
        self.assertTrue(any(issue["type"] == "pending_reagent_must_not_look_verified" for issue in result["issues"]))

    def test_formal_plan_requires_verified_identity(self):
        row = self._valid()
        row["stage"] = "formal_experiment"
        row["developmental_boundary"] = "unknown"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_information_gain_pilot")
        types = {issue["type"] for issue in result["issues"]}
        self.assertIn("formal_requires_verified_reagent_or_na", types)
        self.assertIn("formal_requires_developmental_boundary", types)

    def test_public_style_observation_plan_does_not_require_reagents(self):
        row = self._valid()
        row.update({
            "plan_id": "IG-002", "perturbation": "observation_only", "reagent_identifier": "not_applicable",
            "reagent_identity_status": "not_applicable", "stock_identifier": "not_applicable", "stock_identity_status": "not_applicable",
            "readout": "single-cell expression/localization across ZT", "experimental_unit": "cell",
        })
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_information_gain_pilot")

    def test_public_synthetic_pilots_are_verified(self):
        path = ROOT / "validation" / "synthetic-information-gain-pilots.csv"
        result = validate(path)
        self.assertEqual(result["status"], "verified_information_gain_pilot")
        self.assertEqual(result["n_rows"], 3)


if __name__ == "__main__":
    unittest.main()
