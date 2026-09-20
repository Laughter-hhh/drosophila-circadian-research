import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_candidates import score_row, sensitivity


class CandidateScoringReadoutScopeTests(unittest.TestCase):
    def test_direct_transcript_evidence_is_labeled_molecular_not_functional(self):
        row = {
            "candidate": "Shab",
            "evidence_label": "direct",
            "target_cell_scope": "direct_target_neuron",
            "assay": "single-cell RNA-seq raw UMI detection",
            "readout_match": "expression_or_localization",
        }
        result = score_row(row)
        self.assertEqual(result["directness_gate"], "pass")
        self.assertEqual(result["readout_domain"], "molecular_expression_or_localization")
        self.assertIn("does not establish channel current", result["directness_basis"])
        self.assertIn("membrane-potential rhythm", result["directness_basis"])
        self.assertIsNone(result["score"])
        self.assertEqual(result["shortlist_gate"], "needs_evidence")

    def test_direct_ephys_readout_is_not_causality_without_perturbation(self):
        row = {
            "candidate": "Shal",
            "evidence_label": "direct",
            "target_cell_scope": "direct_target_neuron",
            "assay": "whole-cell electrophysiology",
            "readout_match": "membrane_potential_or_current",
        }
        result = score_row(row)
        self.assertEqual(result["readout_domain"], "electrophysiology_or_membrane_potential_readout")
        self.assertIn("candidate-specific causality still requires", result["directness_basis"])
        self.assertIn("perturbation", result["directness_basis"])

    def test_sensitivity_rule_explains_readout_scoped_directness(self):
        result = sensitivity([{
            "candidate": "Shab",
            "evidence_label": "direct",
            "target_cell_scope": "direct_target_neuron",
            "assay": "single-cell RNA-seq",
            "readout_match": "expression_or_localization",
        }])
        self.assertIn("transcript/localization evidence is not channel-function evidence", result["shortlist_gate_rule"])
        self.assertIn("perturbation and controls", result["shortlist_gate_rule"])


if __name__ == "__main__":
    unittest.main()
