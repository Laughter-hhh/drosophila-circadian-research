import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_candidates import match_target_cells, score_row, sensitivity


def direct_row(candidate="channel", cells="s-LNv"):
    return {
        "candidate": candidate,
        "organism": "Drosophila melanogaster",
        "target_cell_scope": "direct_target_neuron",
        "evidence_target_cells": cells,
        "assay": "whole-cell electrophysiology",
        "readout_match": "membrane_potential_or_current",
        "evidence_label": "direct",
        "expression": "3",
        "electrophysiology": "3",
        "class_match": "3",
    }


class CandidateTargetCellMatchingTests(unittest.TestCase):
    def test_exact_cell_match_can_pass_when_other_gates_pass(self):
        result = score_row(direct_row(), target_cells=["s-LNv"])
        self.assertEqual(result["target_cell_match_status"], "exact")
        self.assertEqual(result["target_cells_supported"], "s-LNv")
        self.assertEqual(result["directness_gate"], "pass")
        self.assertEqual(result["shortlist_gate"], "pass")

    def test_lnv_parent_evidence_does_not_resolve_s_lnv_subtype(self):
        result = score_row(direct_row(cells="LNv"), target_cells=["s-LNv"])
        self.assertEqual(result["target_cell_match_status"], "unresolved")
        self.assertEqual(result["target_cells_unresolved"], "s-LNv")
        self.assertEqual(result["directness_gate"], "conditional_target_cell_scope")
        self.assertEqual(result["shortlist_gate"], "conditional_directness")

    def test_dn1p_is_only_partial_evidence_for_broad_dn_query(self):
        result = score_row(direct_row(cells="DN1p"), target_cells=["DN"])
        self.assertEqual(result["target_cell_match_status"], "partial")
        self.assertEqual(result["target_cells_partially_supported"], "DN")
        self.assertEqual(result["directness_gate"], "partial_target_coverage")
        self.assertEqual(result["shortlist_gate"], "partial_target_coverage")

    def test_different_subtype_is_a_mismatch_not_a_direct_hit(self):
        result = score_row(direct_row(cells="l-LNv"), target_cells=["s-LNv"])
        self.assertEqual(result["target_cell_match_status"], "mismatch")
        self.assertEqual(result["directness_gate"], "needs_direct_evidence")
        self.assertEqual(result["shortlist_gate"], "needs_evidence")

    def test_multiple_requested_subtypes_require_each_to_be_covered(self):
        result = match_target_cells("s-LNv", ["s-LNv", "l-LNv"])
        self.assertEqual(result["target_cell_match_status"], "partial")
        self.assertEqual(result["target_cells_supported"], "s-LNv")
        self.assertEqual(result["target_cells_uncovered"], "l-LNv")

    def test_no_target_query_cannot_assign_target_specific_directness(self):
        result = score_row(direct_row())
        self.assertEqual(result["target_cell_match_status"], "not_requested")
        self.assertEqual(result["directness_gate"], "needs_target_cell_query")
        self.assertEqual(result["shortlist_gate"], "needs_target_cell_query")

    def test_unknown_cell_group_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown cell-group token"):
            match_target_cells("DN1p-ish", ["DN"])

    def test_all_na_candidates_do_not_get_a_phantom_top(self):
        row = direct_row("Shab", "s-LNv")
        for field in ("expression", "electrophysiology", "genetic_tools", "class_match", "rhythmic_evidence", "fly_causal", "cross_species"):
            row[field] = "NA"
        result = sensitivity([row], target_cells=["s-LNv"])
        self.assertEqual(result["ranking_status"], "insufficient_scored_evidence")
        self.assertEqual(result["rankings"]["default"], [])
        self.assertEqual(result["top_candidates"]["default"], None)
        self.assertEqual(result["top_candidate_ties"]["default"], [])
        self.assertIsNone(result["top_candidate_stable"])
        self.assertEqual(result["unscored_candidates"]["default"], ["Shab"])

    def test_tied_scored_candidates_are_not_declared_as_a_single_stable_top(self):
        result = sensitivity([
            direct_row("Shaw", "s-LNv"),
            direct_row("Shal", "s-LNv"),
        ], target_cells=["s-LNv"])
        self.assertEqual(result["top_candidates"]["default"], None)
        self.assertEqual(set(result["top_candidate_ties"]["default"]), {"Shaw", "Shal"})
        self.assertFalse(result["top_candidate_stable"])


    def test_mismatched_or_partial_cell_evidence_cannot_be_called_top(self):
        mismatch = direct_row("l-LNv channel", "l-LNv")
        partial = direct_row("DN1p channel", "DN1p")
        result_lnd = sensitivity([mismatch], target_cells=["LNd"])
        result_dn = sensitivity([partial], target_cells=["DN"])
        self.assertEqual(result_lnd["rankings"]["default"], ["l-LNv channel"])
        self.assertEqual(result_lnd["top_candidates"]["default"], None)
        self.assertEqual(result_lnd["top_candidate_ties"]["default"], [])
        self.assertEqual(result_lnd["top_candidate_status"]["default"], "no_target_scoped_scored_candidates")
        self.assertIsNone(result_lnd["top_candidate_stable"])
        self.assertEqual(result_dn["rankings"]["default"], ["DN1p channel"])
        self.assertEqual(result_dn["top_candidates"]["default"], None)
        self.assertEqual(result_dn["top_candidate_status"]["default"], "no_target_scoped_scored_candidates")
        self.assertIsNone(result_dn["top_candidate_stable"])


if __name__ == "__main__":
    unittest.main()

