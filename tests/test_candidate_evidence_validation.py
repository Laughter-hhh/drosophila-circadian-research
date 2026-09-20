import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_candidate_evidence import validate


FIELDS = [
    "candidate", "class", "organism", "target_cell_scope", "assay", "readout_match", "evidence_label",
    "expression", "electrophysiology", "genetic_tools", "class_match", "rhythmic_evidence", "fly_causal", "cross_species",
    "keep_drop_reason", "sources", "confidence", "evidence_notes",
]


class CandidateEvidenceValidationTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _valid_row(self):
        row = {field: "NA" for field in FIELDS}
        row.update({
            "candidate": "Shaw", "class": "gated_Kv3", "organism": "Drosophila melanogaster",
            "target_cell_scope": "direct_target_neuron", "assay": "whole-cell electrophysiology",
            "readout_match": "membrane_potential_or_current", "evidence_label": "direct",
            "expression": "3", "sources": "synthetic-source", "confidence": "high",
            "keep_drop_reason": "retain for pilot", "evidence_notes": "Conclusion|direct target-neuron current evidence.",
        })
        return row

    def test_valid_row_requires_traceability_fields(self):
        path = self._write(self._valid_row())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_candidate_evidence_table")
        self.assertEqual(result["n_rows"], 1)

    def test_rated_row_without_sources_is_rejected(self):
        row = self._valid_row()
        row["sources"] = "NA"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "missing_sources_for_rated_evidence" for issue in result["issues"]))

    def test_direct_label_without_target_neuron_scope_is_rejected(self):
        row = self._valid_row()
        row["target_cell_scope"] = "nearby_clock_neuron"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "direct_label_without_target_assay_readout" for issue in result["issues"]))

    def test_invalid_evidence_label_is_rejected(self):
        row = self._valid_row()
        row["evidence_label"] = "maybe"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "invalid_evidence_label" for issue in result["issues"]))

    def test_public_candidate_table_passes_structured_schema(self):
        path = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        result = validate(path)
        self.assertEqual(result["status"], "verified_candidate_evidence_table")
        self.assertEqual(result["n_rows"], 15)


if __name__ == "__main__":
    unittest.main()
