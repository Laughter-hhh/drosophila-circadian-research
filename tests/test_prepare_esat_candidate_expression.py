import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_esat_candidate_expression import prepare_esat_candidate_expression


class PrepareEsatCandidateExpressionTests(unittest.TestCase):
    def _write_inputs(self, directory: Path):
        matrix = directory / "matrix.tsv.gz"
        with gzip.open(matrix, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["Symbol", "", "S2", "S1"])
            writer.writerows([
                ["FBtrSh1", "Sh", "10", "12"],
                ["FBtrSh2", "Sh", "3", "4"],
                ["FBtrIr1", "Ir", "5", "8"],
                ["FBtrOther", "other", "1", "2"],
            ])

        metadata = directory / "metadata.csv"
        fields = [
            "matrix_path", "sample_id", "geo_accession", "cell_type", "ZT_or_CT",
            "time_hours", "time_system", "timecourse_id", "background",
            "experimental_unit", "biological_replicate_id",
        ]
        with metadata.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            # Deliberately reverse the matrix header order; sample identity, not row order, is the key.
            for sample, gsm, time in (("S1", "GSM1", 0), ("S2", "GSM2", 12)):
                writer.writerow({
                    "matrix_path": matrix.as_posix(),
                    "sample_id": sample,
                    "geo_accession": gsm,
                    "cell_type": "LNv",
                    "ZT_or_CT": f"ZT{time}",
                    "time_hours": str(time),
                    "time_system": "ZT",
                    "timecourse_id": "course_1",
                    "background": "unknown",
                    "experimental_unit": "pooled_neuron_library",
                    "biological_replicate_id": gsm,
                })

        candidates = directory / "candidates.csv"
        with candidates.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["candidate", "class"])
            writer.writeheader()
            writer.writerows([
                {"candidate": "Sh", "class": "gated"},
                {"candidate": "Irk1", "class": "leak"},
                {"candidate": "absent", "class": "unknown"},
            ])

        aliases = directory / "aliases.csv"
        with aliases.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "matrix_symbol", "canonical_gene_symbol", "source_url", "checked_at_utc", "evidence_note",
            ])
            writer.writeheader()
            writer.writerow({
                "matrix_symbol": "Ir",
                "canonical_gene_symbol": "Irk1",
                "source_url": "https://flybase.org/reports/FBgn0265042",
                "checked_at_utc": "2026-09-22T00:00:00Z",
                "evidence_note": "Source documents Ir as an alternate name for Irk1.",
            })
        return matrix, metadata, candidates, aliases

    def test_preserves_transcripts_and_emits_explicit_aggregations_and_alias_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix, metadata, candidates, aliases = self._write_inputs(Path(tmp))
            result = prepare_esat_candidate_expression(
                [("LNv", matrix)], metadata, candidates, "candidate", "class", aliases,
            )

        self.assertEqual(len(result["transcript_rows"]), 6)
        audit = result["audit"]
        self.assertEqual(audit["normalization_status"], "none_added_processed_numeric_scale_preserved")
        self.assertEqual(audit["n_candidates"], 3)
        self.assertEqual(audit["matrix_audits"][0]["sample_columns"], ["S2", "S1"])

        sums = {(row["gene_symbol"], row["sample_id"]): row for row in result["sample_rows"]["sum"]}
        medians = {(row["gene_symbol"], row["sample_id"]): row for row in result["sample_rows"]["median"]}
        maxima = {(row["gene_symbol"], row["sample_id"]): row for row in result["sample_rows"]["max"]}
        self.assertEqual(sums[("Sh", "S2")]["expression"], "13")
        self.assertEqual(medians[("Sh", "S2")]["expression"], "6.5")
        self.assertEqual(maxima[("Sh", "S2")]["expression"], "10")
        self.assertEqual(sums[("Irk1", "S1")]["expression"], "8")
        self.assertEqual(sums[("absent", "S1")]["status"], "not_represented_in_processed_matrix")
        self.assertEqual(sums[("absent", "S1")]["expression"], "")
        self.assertEqual(sums[("Sh", "S1")]["geo_accession"], "GSM1")
        self.assertEqual(sums[("Sh", "S1")]["expression_unit"], "processed_value_unit_unspecified")

    def test_matrix_metadata_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix, metadata, candidates, aliases = self._write_inputs(Path(tmp))
            with metadata.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["sample_id"] = "NOT_A_MATRIX_COLUMN"
            with metadata.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "matrix/metadata sample mismatch"):
                prepare_esat_candidate_expression(
                    [("LNv", matrix)], metadata, candidates, "candidate", "class", aliases,
                )

    def test_duplicate_candidate_transcript_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix, metadata, candidates, aliases = self._write_inputs(Path(tmp))
            with gzip.open(matrix, "at", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
                writer.writerow(["FBtrSh1", "Sh", "9", "9"])
            with self.assertRaisesRegex(ValueError, "duplicate candidate transcript ID"):
                prepare_esat_candidate_expression(
                    [("LNv", matrix)], metadata, candidates, "candidate", "class", aliases,
                )


if __name__ == "__main__":
    unittest.main()
