import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_esat_candidate_sample_keys import _read_aliases, audit_matrix


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

    def test_explicit_source_documented_alias_maps_to_candidate_without_implying_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = self._write_matrix(directory, [["FBtrIr1", "Ir", "4", "8"]])
            alias_path = directory / "aliases.csv"
            with alias_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "matrix_symbol", "canonical_gene_symbol", "source_url", "checked_at_utc", "evidence_note",
                ])
                writer.writeheader()
                writer.writerow({
                    "matrix_symbol": "Ir",
                    "canonical_gene_symbol": "Irk1",
                    "source_url": "https://flybase.org/reports/FBgn0265042",
                    "checked_at_utc": "2026-09-22T00:00:00Z",
                    "evidence_note": "FlyBase lists Ir as an alternate name for Irk1.",
                })
            aliases = _read_aliases(alias_path, ["Irk1"])
            result = audit_matrix("LNv", path, ["Irk1"], aliases)

        self.assertEqual(aliases, {"ir": "Irk1"})
        self.assertEqual(result["n_candidates_with_symbol_rows"], 1)
        candidate = result["candidate_audits"][0]
        self.assertEqual(candidate["matrix_symbols"], ["Ir"])
        self.assertEqual(candidate["symbol_match_modes"], {"explicit_alias_map": 1})

    def test_alias_target_must_be_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = Path(tmp) / "aliases.csv"
            with alias_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "matrix_symbol", "canonical_gene_symbol", "source_url", "checked_at_utc", "evidence_note",
                ])
                writer.writeheader()
                writer.writerow({
                    "matrix_symbol": "Ir",
                    "canonical_gene_symbol": "not_in_candidates",
                    "source_url": "https://example.org/source",
                    "checked_at_utc": "2026-09-22T00:00:00Z",
                    "evidence_note": "test fixture",
                })
            with self.assertRaisesRegex(ValueError, "not an exact symbol in the candidate list"):
                _read_aliases(alias_path, ["Irk1"])


if __name__ == "__main__":
    unittest.main()
