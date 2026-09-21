import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_candidate_evidence import validate


class CandidateSearchLogGateTests(unittest.TestCase):
    def test_public_candidate_table_links_to_checked_search_log(self):
        table = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        log = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        result = validate(table, log)
        self.assertEqual(result["status"], "verified_candidate_evidence_table")
        self.assertEqual(result["evidence_search_log"]["status"], "verified_evidence_search_log")
        self.assertEqual(result["n_rows"], 15)

    def test_direct_candidate_cell_scope_must_match_checked_log(self):
        table_source = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        log = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        with table_source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rows[0]["evidence_target_cells"] = "DN1p"
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "candidate.csv"
            with table.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            result = validate(table, log)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "direct_candidate_not_supported_by_matching_log_cells" for issue in result["issues"]))

    def test_near_direct_readout_cannot_union_cells_from_an_unmatched_source_scope(self):
        table_source = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        log_source = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        with table_source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        irk1 = next(row for row in rows if row["candidate"] == "Irk1")
        irk1.update({
            "target_cell_scope": "direct_target_neuron",
            "evidence_target_cells": "s-LNv;l-LNv",
            "assay": "s-LNv ClopHensor and in-vivo genetics; S2-R+ cultured-cell whole-cell patch clamp",
            "readout_match": "membrane_potential_or_current",
            "evidence_label": "near_direct",
        })
        with log_source.open(newline="", encoding="utf-8") as handle:
            log_rows = list(csv.DictReader(handle))
            log_fields = list(log_rows[0])
        ephys = next(row for row in log_rows if row["candidate"] == "Irk1" and row["readout_match"] == "membrane_potential_or_current")
        ephys.update({
            "target_cell_scope": "direct_target_neuron",
            "evidence_target_cells": "s-LNv",
            "assay": "s-LNv ClopHensor and in-vivo genetics; S2-R+ cultured-cell whole-cell patch clamp",
            "evidence_label": "near_direct",
        })
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "candidate.csv"
            log = Path(directory) / "search-log.csv"
            with table.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator=chr(10))
                writer.writeheader()
                writer.writerows(rows)
            with log.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=log_fields, lineterminator=chr(10))
                writer.writeheader()
                writer.writerows(log_rows)
            result = validate(table, log)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "near_direct_candidate_not_supported_by_matching_log_cells" for issue in result["issues"]))

    def test_candidate_missing_from_search_log_is_blocked(self):
        source = ROOT / "validation" / "synthetic-candidate-evidence.csv"
        lines = source.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].replace("Sh,", "SyntheticOnly,", 1)
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "candidate.csv"
            table.write_text("\n".join(lines) + "\n", encoding="utf-8")
            log = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
            result = validate(table, log)
        self.assertEqual(result["status"], "invalid_candidate_evidence_table")
        self.assertTrue(any(issue["type"] == "candidate_missing_from_search_log" for issue in result["issues"]))

    def test_source_log_scorer_cli_runs_as_documented(self):
        candidate = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        log = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ranked.csv"
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--search-log", str(log), "--readout-match", "membrane_potential_or_current",
                "--target-cell", "s-LNv", "--output", str(output),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with output.open(newline="", encoding="utf-8") as handle:
                irk1 = next(row for row in csv.DictReader(handle) if row["candidate"] == "Irk1")
        self.assertEqual(irk1["directness_gate"], "needs_direct_evidence")

    def test_real_scored_current_table_requires_a_search_log(self):
        candidate = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ranked.csv"
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--target-cell", "s-LNv", "--output", str(output),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--search-log and --readout-match are required", completed.stderr)
            self.assertFalse(output.exists())

    def test_scored_noncurrent_table_requires_a_search_log(self):
        source = ROOT / "validation" / "public-data" / "GSE157504_candidate_evidence_handoff.csv"
        with source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rows[0]["expression"] = "2"
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.csv"
            output = Path(directory) / "ranked.csv"
            with candidate.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--target-cell", "s-LNv", "--output", str(output),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--search-log and --readout-match are required", completed.stderr)
            self.assertFalse(output.exists())

    def test_all_na_current_table_requires_a_search_log(self):
        source = ROOT / "validation" / "public-data" / "GSE157504_candidate_evidence_handoff.csv"
        with source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        for row in rows:
            row["readout_match"] = "membrane_potential_or_current"
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.csv"
            output = Path(directory) / "ranked.csv"
            with candidate.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--target-cell", "s-LNv", "--output", str(output),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--search-log and --readout-match are required", completed.stderr)
            self.assertFalse(output.exists())

    def test_scorer_revalidates_candidate_table_against_search_log(self):
        candidate_source = ROOT / "validation" / "public-data" / "candidate-evidence-real.csv"
        log = ROOT / "validation" / "public-data" / "candidate-evidence-search-log.csv"
        with candidate_source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        irk1 = next(row for row in rows if row["candidate"] == "Irk1")
        irk1.update({
            "target_cell_scope": "direct_target_neuron",
            "evidence_target_cells": "s-LNv;l-LNv",
            "assay": "native s-LNv/l-LNv whole-cell patch clamp",
            "readout_match": "membrane_potential_or_current",
            "evidence_label": "near_direct",
        })
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.csv"
            output = Path(directory) / "ranked.csv"
            with candidate.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--search-log", str(log), "--readout-match", "membrane_potential_or_current",
                "--target-cell", "s-LNv", "--output", str(output),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("candidate table and search log failed joint validation", completed.stderr)
            self.assertIn("candidate_readout_not_supported_by_linked_search_log", completed.stderr)
            self.assertFalse(output.exists())

    def test_all_na_transcript_diagnostic_remains_unranked_without_log(self):
        candidate = ROOT / "validation" / "public-data" / "GSE157504_candidate_evidence_handoff.csv"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "diagnostic.csv"
            sensitivity = Path(directory) / "sensitivity.json"
            command = [
                sys.executable, str(ROOT / "scripts" / "score_candidates.py"), str(candidate),
                "--target-cell", "s-LNv", "--target-cell", "l-LNv", "--target-cell", "LNd", "--target-cell", "DN",
                "--output", str(output), "--sensitivity-output", str(sensitivity),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with output.open(newline="", encoding="utf-8") as handle:
                diagnostic_rows = list(csv.DictReader(handle))
            sensitivity_result = json.loads(sensitivity.read_text(encoding="utf-8"))
        self.assertEqual(len(diagnostic_rows), 15)
        self.assertTrue(all(row["score"] == "" for row in diagnostic_rows))
        self.assertTrue(all(row["shortlist_gate"] == "needs_evidence" for row in diagnostic_rows))
        self.assertEqual(sensitivity_result["ranking_status"], "insufficient_scored_evidence")
        self.assertTrue(all(not candidates for candidates in sensitivity_result["rankings"].values()))
        self.assertTrue(all(candidate is None for candidate in sensitivity_result["top_candidates"].values()))


if __name__ == "__main__":
    unittest.main()
