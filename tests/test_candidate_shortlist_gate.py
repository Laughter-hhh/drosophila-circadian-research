import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_candidates import rank_rows, sensitivity


class CandidateShortlistGateTests(unittest.TestCase):
    def test_low_coverage_candidate_is_not_shortlist_gate_pass(self):
        rows = [
            {"candidate": "class-only", "class_match": "3"},
            {"candidate": "multi-evidence", "expression": "2", "electrophysiology": "2", "class_match": "2"},
        ]
        ranked = rank_rows(rows)
        by_name = {row["candidate"]: row for row in ranked}
        self.assertEqual(by_name["class-only"]["coverage_gate"], "needs_evidence")
        self.assertEqual(by_name["multi-evidence"]["coverage_gate"], "pass")
        self.assertNotEqual(by_name["multi-evidence"]["shortlist_gate"], "pass")

    def test_sensitivity_reports_gate_pass_candidates_separately(self):
        direct = {
            "candidate": "strong", "expression": "3", "electrophysiology": "3", "class_match": "3",
            "organism": "Drosophila melanogaster", "target_cell_scope": "direct_target_neuron", "evidence_target_cells": "s-LNv",
            "assay": "whole-cell electrophysiology", "readout_match": "membrane_potential_or_current", "evidence_label": "direct",
        }
        weak = {"candidate": "weak", "class_match": "3"}
        result = sensitivity([direct, weak], target_cells=["s-LNv"])
        self.assertIn("shortlist_gate_pass", result)
        self.assertEqual(result["shortlist_gate_pass"]["default"], ["strong"])

    def test_near_direct_candidate_is_reported_as_conditional(self):
        row = {
            "candidate": "Irk1", "expression": "3", "electrophysiology": "2", "class_match": "3",
            "target_cell_scope": "direct_target_neuron", "evidence_target_cells": "s-LNv", "assay": "cultured-cell electrophysiology",
            "readout_match": "membrane_potential_or_current", "evidence_label": "near_direct",
        }
        result = rank_rows([row], target_cells=["s-LNv"])[0]
        self.assertEqual(result["directness_gate"], "conditional")
        self.assertEqual(result["shortlist_gate"], "conditional_directness")


if __name__ == "__main__":
    unittest.main()
