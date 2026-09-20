import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_candidates import rank_rows, score_row, sensitivity


def _direct(candidate="direct"):
    return {
        "candidate": candidate,
        "organism": "Drosophila melanogaster",
        "target_cell_scope": "direct_target_neuron",
        "evidence_target_cells": "s-LNv",
        "assay": "whole-cell electrophysiology",
        "readout_match": "membrane_potential_or_current",
        "evidence_label": "direct",
    }


class CandidateScoringTests(unittest.TestCase):
    def test_na_is_excluded_from_denominator_but_reduces_adjusted_score(self):
        row = {"candidate": "A", "expression": "3", "electrophysiology": "NA"}
        result = score_row(row)
        self.assertEqual(result["score"], 100.0)
        self.assertLess(result["coverage"], 1.0)
        self.assertLess(result["coverage_adjusted_score"], result["score"])
        self.assertEqual(result["observed_dimensions"], 1)

    def test_weight_sensitivity_is_explicit(self):
        direct_expression = _direct("expression-led")
        direct_expression.update({"expression": "3", "electrophysiology": "3", "genetic_tools": "0", "class_match": "0", "rhythmic_evidence": "0", "fly_causal": "0", "cross_species": "0"})
        direct_tools = _direct("tools-led")
        direct_tools.update({"expression": "1", "electrophysiology": "1", "genetic_tools": "2", "class_match": "2", "rhythmic_evidence": "2", "fly_causal": "2", "cross_species": "2"})
        result = sensitivity([direct_expression, direct_tools], target_cells=["s-LNv"])
        self.assertIn("rankings", result)
        self.assertIn("top_candidates", result)
        self.assertEqual(set(result["top_candidates"].values()), {"expression-led", "tools-led"})
        self.assertIn("coverage_adjusted_score", result["ranking_rule"])

    def test_rank_uses_coverage_to_avoid_single_dimension_false_top(self):
        rows = [
            {"candidate": "class-only", "class_match": "3"},
            {"candidate": "multi-evidence", "expression": "2", "electrophysiology": "2", "class_match": "2"},
        ]
        ranked = rank_rows(rows)
        self.assertEqual(ranked[0]["candidate"], "multi-evidence")
        self.assertGreater(ranked[0]["coverage"], ranked[1]["coverage"])

    def test_rank_contains_coverage_for_incomplete_evidence(self):
        rows = [
            {"candidate": "A", "expression": "3", "electrophysiology": "NA"},
            {"candidate": "B", "expression": "2", "electrophysiology": "2"},
        ]
        ranked = rank_rows(rows)
        self.assertEqual(ranked[0]["candidate"], "B")
        self.assertIn("coverage", ranked[0])

    def test_directness_gate_requires_target_assay_and_readout(self):
        row = _direct("Shaw")
        row.update({"expression": "3", "electrophysiology": "3", "class_match": "3"})
        result = score_row(row, target_cells=["s-LNv"])
        self.assertEqual(result["directness_gate"], "pass")
        self.assertEqual(result["shortlist_gate"], "pass")

    def test_indirect_candidate_cannot_be_direct_shortlist_pass(self):
        row = {"candidate": "indirect", "expression": "3", "electrophysiology": "3", "class_match": "3", "evidence_label": "indirect", "target_cell_scope": "indirect_or_unverified", "assay": "behavior", "readout_match": "behavior_only"}
        result = score_row(row)
        self.assertEqual(result["directness_gate"], "needs_direct_evidence")
        self.assertNotEqual(result["shortlist_gate"], "pass")


if __name__ == "__main__":
    unittest.main()
