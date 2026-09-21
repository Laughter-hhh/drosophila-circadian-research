import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_expression_rhythm import analyze_expression_samples


class ExpressionRhythmTests(unittest.TestCase):
    def _write(self, rows):
        fd, name = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        path = Path(name)
        fields = ["gene_symbol", "sample_id", "cell_type", "time", "background", "developmental_stage", "sex", "gender", "timecourse_id", "expression"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_fit_and_insufficiency_are_distinguished(self):
        rows = []
        for gene, times in (("Sh", (0, 6, 12, 18)), ("para", (0, 12))):
            for idx, time in enumerate(times):
                rows.append({"gene_symbol": gene, "sample_id": f"{gene}{idx}", "cell_type": "s-LNv", "time": f"ZT{time}", "background": "yw", "expression": str(1 + idx)})
        path = self._write(rows)
        try:
            result = analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        sh = [row for row in result if row["gene_symbol"] == "Sh"][0]
        para = [row for row in result if row["gene_symbol"] == "para"][0]
        self.assertEqual(sh["status"], "exploratory_fixed_period_cosinor")
        self.assertEqual(sh["time_system"], "ZT")
        self.assertEqual(sh["n_unique_time_points"], 4)
        self.assertEqual(para["status"], "insufficient_or_invalid_time_series")

    def test_mismatched_time_basis_blocks_the_whole_run(self):
        path = self._write([
            {"gene_symbol": "Sh", "sample_id": f"s{idx}", "cell_type": "s-LNv", "time": f"CT{time}", "background": "yw", "expression": "1"}
            for idx, time in enumerate((0, 6, 12, 18))
        ])
        try:
            with self.assertRaisesRegex(ValueError, "time system mismatch"):
                analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)

    def test_time_system_is_required(self):
        path = self._write([])
        try:
            with self.assertRaisesRegex(ValueError, "time_system must be ZT or CT"):
                analyze_expression_samples(path)
        finally:
            path.unlink(missing_ok=True)

    def test_duplicate_sample_id_is_rejected_even_if_one_row_has_no_expression(self):
        rows = [
            {"gene_symbol": "Sh", "sample_id": "s0", "cell_type": "s-LNv", "time": "ZT0", "background": "yw", "expression": "1"},
            {"gene_symbol": "Sh", "sample_id": "s0", "cell_type": "s-LNv", "time": "ZT0", "background": "yw", "expression": ""},
            *[
                {"gene_symbol": "Sh", "sample_id": f"s{idx}", "cell_type": "s-LNv", "time": f"ZT{time}", "background": "yw", "expression": str(idx + 1)}
                for idx, time in enumerate((6, 12, 18), start=1)
            ],
        ]
        path = self._write(rows)
        try:
            with self.assertRaisesRegex(ValueError, "duplicate sample_id.*aggregate probes/transcripts"):
                analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)

    def test_same_sample_id_in_distinct_backgrounds_is_allowed(self):
        rows = [
            {"gene_symbol": "Sh", "sample_id": f"s{idx}", "cell_type": "s-LNv", "time": f"ZT{time}", "background": background, "expression": str(idx + 1)}
            for background in ("yw", "per01")
            for idx, time in enumerate((0, 6, 12, 18))
        ]
        path = self._write(rows)
        try:
            result = analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["status"] == "exploratory_fixed_period_cosinor" for row in result))

    def test_timecourses_are_fit_separately_and_reported(self):
        rows = []
        for course, offset in (("course_A", 0), ("course_B", 100)):
            for index, time in enumerate((0, 4, 8, 12, 16, 20)):
                rows.append({
                    "gene_symbol": "Sh",
                    "sample_id": f"{course}_{index}",
                    "cell_type": "LNv",
                    "time": f"ZT{time}",
                    "background": "yw",
                    "timecourse_id": course,
                    "expression": str(offset + index + 1),
                })
        path = self._write(rows)
        try:
            result = analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual({row["timecourse_id"] for row in result}, {"course_A", "course_B"})
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["n_observations"] == 6 for row in result))
        self.assertTrue(all("pooled libraries" in row["replication_unit_warning"] for row in result))


    def test_sex_and_developmental_stage_strata_are_not_collapsed(self):
        rows = []
        for stage in ("adult", "larva"):
            for sex in ("female", "male"):
                for index, time in enumerate((0, 6, 12, 18)):
                    row = {
                        "gene_symbol": "Sh",
                        "sample_id": f"{stage}_{sex}_{time}",
                        "cell_type": "LNd",
                        "time": f"ZT{time}",
                        "background": "yw",
                        "developmental_stage": stage,
                        "expression": str(10 + index),
                    }
                    row["sex" if sex == "female" else "gender"] = sex
                    rows.append(row)
        path = self._write(rows)
        try:
            result = analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(len(result), 4)
        self.assertEqual(
            {(row["sex"], row["developmental_stage"]) for row in result},
            {(sex, stage) for sex in ("female", "male") for stage in ("adult", "larva")},
        )
        self.assertTrue(all(row["status"] == "exploratory_fixed_period_cosinor" for row in result))

    def test_conflicting_context_for_same_sample_id_is_blocked(self):
        path = self._write([
            {"gene_symbol": "Sh", "sample_id": "same", "cell_type": "LNd", "time": "ZT0", "background": "yw", "sex": "female", "developmental_stage": "adult", "expression": "1"},
            {"gene_symbol": "Sh", "sample_id": "same", "cell_type": "LNd", "time": "ZT0", "background": "yw", "gender": "male", "developmental_stage": "adult", "expression": "1"},
        ])
        try:
            with self.assertRaisesRegex(ValueError, "conflicting sex/developmental_stage metadata"):
                analyze_expression_samples(path, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)


    def test_gse22308_output_retains_stage_and_sex_strata(self):
        public_data = ROOT / "validation" / "public-data"
        result = analyze_expression_samples(
            public_data / "GSE22308_candidate_expression_samples.csv",
            time_system="ZT",
        )
        sh_large = [
            row for row in result
            if row.get("gene_symbol") == "Sh"
            and row.get("cell_type") == "large PDF circadian neurons"
            and row.get("background") == "yw"
        ]
        self.assertEqual(len(sh_large), 1)
        self.assertEqual(sh_large[0]["developmental_stage"], "adult")
        self.assertEqual(sh_large[0]["sex"], "male and female")


if __name__ == "__main__":
    unittest.main()
