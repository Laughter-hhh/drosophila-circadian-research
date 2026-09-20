import csv
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


if __name__ == "__main__":
    unittest.main()
