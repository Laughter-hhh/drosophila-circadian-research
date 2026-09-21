import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_evidence_search_log import parse_cell_tokens, validate


FIELDS = [
    "record_id", "candidate", "query", "database", "search_date", "source_id", "source_url_or_identifier", "source_type",
    "organism", "target_cell_scope", "evidence_target_cells", "assay", "readout_match", "evidence_label", "claim_type", "source_support_status",
    "result_summary", "decision", "decision_reason",
]


class EvidenceSearchLogTests(unittest.TestCase):
    def _write(self, row):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
        handle.close()
        return Path(handle.name)

    def _valid(self):
        return {
            "record_id": "rec-001", "candidate": "Shaw", "query": "Shaw LNv circadian current",
            "database": "PubMed", "search_date": "2026-09-06", "source_id": "PMID:31612994",
            "source_url_or_identifier": "https://pubmed.ncbi.nlm.nih.gov/31612994/", "source_type": "primary_paper",
            "organism": "Drosophila melanogaster", "target_cell_scope": "direct_target_neuron", "evidence_target_cells": "s-LNv;l-LNv",
            "assay": "whole-cell electrophysiology", "readout_match": "membrane_potential_or_current",
            "evidence_label": "direct", "claim_type": "conclusion", "source_support_status": "checked",
            "result_summary": "Circadian Shaw current was measured in clock neurons.", "decision": "include",
            "decision_reason": "Direct target-neuron current evidence meets the first-pass gate.",
        }

    def test_valid_log_is_verified(self):
        path = self._write(self._valid())
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_evidence_search_log")

    def test_direct_claim_requires_checked_source_and_matched_scope(self):
        row = self._valid()
        row["source_support_status"] = "not_checked"
        row["target_cell_scope"] = "nearby_clock_neuron"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_evidence_search_log")
        types = {issue["type"] for issue in result["issues"]}
        self.assertIn("direct_label_without_target_assay_readout", types)
        self.assertIn("direct_label_requires_checked_source", types)

    def test_direct_log_requires_named_evidence_target_cells(self):
        row = self._valid()
        row["evidence_target_cells"] = "unverified"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_evidence_search_log")
        self.assertTrue(any(issue["type"] == "direct_label_without_evidence_target_cells" for issue in result["issues"]))

    def test_unverified_cannot_be_included(self):
        row = self._valid()
        row.update({"evidence_label": "unverified", "target_cell_scope": "none_or_unverified", "readout_match": "none_or_unverified", "decision": "include"})
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_evidence_search_log")
        self.assertTrue(any(issue["type"] == "unverified_cannot_be_directly_included" for issue in result["issues"]))

    def test_thesis_source_is_rejected(self):
        row = self._valid()
        row["source_url_or_identifier"] = "https://example.org/thesis/123"
        path = self._write(row)
        try:
            result = validate(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "invalid_evidence_search_log")
        self.assertTrue(any(issue["type"] == "thesis_source_not_allowed" for issue in result["issues"]))

    def test_parse_cell_tokens_canonicalizes_aliases(self):
        self.assertEqual(parse_cell_tokens("ln(v);DN1p;ln_itp"), ["LNv", "DN1p", "LN_ITP_ambiguous"])

    def test_parse_cell_tokens_rejects_unknown_and_mixed_unknown(self):
        with self.assertRaises(ValueError):
            parse_cell_tokens("LNv;DN1x")
        with self.assertRaises(ValueError):
            parse_cell_tokens("unverified;s-LNv")

    def test_public_candidate_search_log_is_verified(self):
        path = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        result = validate(path)
        self.assertEqual(result["status"], "verified_evidence_search_log")
        self.assertEqual(result["n_rows"], 19)


if __name__ == "__main__":
    unittest.main()
