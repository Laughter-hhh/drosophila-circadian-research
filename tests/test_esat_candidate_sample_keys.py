import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_esat_candidate_sample_keys import audit_matrix


class EsatCandidateSampleKeyTests(unittest.TestCase):
    def _write_matrix(self, directory: Path, rows, compressed=False) -> Path:
        path = directory / ("matrix.tsv.gz" if compressed else "matrix.tsv")
        opener = gzip.open if compressed else open
        with opener(path, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["Symbol", "", "sample_A", "sample_B"])
            writer.writerows(rows)
        return path

    def test_counts_transcripts_without_calling_them_replicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = self._write_matrix(directory, [
                ["FBtr1", "Sh", "10", "12"],
                ["FBtr2", "sh", "3", "4"],
                ["FBtr3", "para", "1", "2"],
                ["FBtr4", "other", "5", "6"],
            ], compressed=True)
            result = audit_matrix("LNv", path, ["Sh", "para", "missing"])

        self.assertEqual(result["n_sample_columns"], 2)
        self.assertEqual(result["n_candidates_with_symbol_rows"], 2)
        self.assertEqual(result["candidate_symbols_not_found"], ["missing"])
        self.assertEqual(result["n_candidate_gene_sample_pairs_with_multiple_feature_rows"], 2)
        by_symbol = {row["candidate_symbol"]: row for row in result["candidate_audits"]}
        self.assertEqual(by_symbol["Sh"]["n_transcript_rows"], 2)
        self.assertEqual(by_symbol["Sh"]["status"], "multiple_transcript_rows_per_sample")
        self.assertEqual(by_symbol["para"]["status"], "single_transcript_row_per_sample")

    def test_duplicate_sample_column_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "matrix.tsv"
            path.write_text("Symbol\t\tS1\tS1\nFBtr1\tSh\t1\t2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate sample-column labels"):
                audit_matrix("LNv", path, ["Sh"])

    def test_malformed_row_width_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "matrix.tsv"
            path.write_text("Symbol\t\tS1\tS2\nFBtr1\tSh\t1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected 4"):
                audit_matrix("LNv", path, ["Sh"])


if __name__ == "__main__":
    unittest.main()
