import csv
import gzip
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_gse157504_candidate_detection.py"


class GSE157504CandidateDetectionTests(unittest.TestCase):
    def _fixture(self, root: Path, include_unmatched: bool = False):
        ld_id = "20200101_CLK_LD_zt02_AA_ACGT"
        dd_id = "20200101_CLK_DD_zt06_AA_TGCA"
        annotation_path = root / "annotation.csv"
        with annotation_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("", "experiment", "time", "Repeats", "Idents"))
            writer.writeheader()
            writer.writerow({"": ld_id, "experiment": "CLK_LD", "time": "zt02", "Repeats": "LD_1", "Idents": "2:s_LNv"})
            writer.writerow({"": dd_id, "experiment": "CLK_DD", "time": "zt06", "Repeats": "DD_2", "Idents": "3:DN1a"})
            if include_unmatched:
                writer.writerow({"": "20200101_CLK_LD_zt10_AA_MISSING", "experiment": "CLK_LD", "time": "zt10", "Repeats": "LD_1", "Idents": "5:LNd_Trissin"})

        candidate_path = root / "candidates.csv"
        with candidate_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("gene_symbol", "priority_class"))
            writer.writeheader()
            writer.writerow({"gene_symbol": "Shab", "priority_class": "leak_or_gated"})
            writer.writerow({"gene_symbol": "para", "priority_class": "gated_Na"})

        matrix = io.StringIO(newline="")
        writer = csv.writer(matrix, lineterminator="\n")
        raw_dd_id = dd_id.replace("_zt06_", "_CT06_")
        writer.writerow(["", "X" + ld_id, "X" + raw_dd_id, "unannotated-cell"])
        writer.writerow(["Shab", 2, 0, 9])
        writer.writerow(["Irk1", 1, 4, 8])
        compressed = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as gz:
            gz.write(matrix.getvalue().encode("utf-8"))
        raw_path = root / "raw.tar"
        member_bytes = compressed.getvalue()
        with tarfile.open(raw_path, mode="w") as archive:
            member = tarfile.TarInfo("sample.csv.gz")
            member.size = len(member_bytes)
            archive.addfile(member, io.BytesIO(member_bytes))
        return raw_path, annotation_path, candidate_path

    def _run(self, root: Path, include_unmatched: bool = False):
        raw_path, annotation_path, candidate_path = self._fixture(root, include_unmatched)
        paths = {
            "sample": root / "sample.csv",
            "group": root / "group.csv",
            "feature": root / "feature.csv",
            "report": root / "report.json",
        }
        command = [
            sys.executable, str(SCRIPT), str(raw_path), str(annotation_path), str(candidate_path),
            "--provenance-root", str(root), "--sample-output", str(paths["sample"]),
            "--group-output", str(paths["group"]), "--feature-output", str(paths["feature"]),
            "--report-output", str(paths["report"]),
        ]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        return completed, paths

    def test_condition_aware_join_and_descriptive_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, paths = self._run(Path(temporary))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(paths["report"].read_text(encoding="utf-8"))
            self.assertTrue(report["join"]["join_complete"])
            self.assertEqual(report["join"]["n_annotation_cells"], 2)
            self.assertEqual(report["join"]["n_raw_matrix_cell_columns"], 3)
            self.assertEqual(report["join"]["n_unannotated_raw_columns"], 1)
            with paths["group"].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_condition = {row["condition"]: row for row in rows if row["candidate"] == "Shab"}
            self.assertEqual(by_condition["LD"]["cell_group"], "s-LNv")
            self.assertEqual(by_condition["LD"]["time_system"], "ZT")
            self.assertEqual(by_condition["LD"]["detection_fraction"], "1")
            self.assertEqual(by_condition["DD"]["cell_group"], "DN")
            self.assertEqual(by_condition["DD"]["time_system"], "CT")
            self.assertEqual(by_condition["DD"]["detection_fraction"], "0")
            with paths["feature"].open(newline="", encoding="utf-8") as handle:
                features = {row["candidate"]: row for row in csv.DictReader(handle)}
            self.assertEqual(features["para"]["raw_feature_status"], "not_represented_in_raw_features_not_evaluable")

    def test_incomplete_annotation_join_is_nonzero_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, paths = self._run(Path(temporary), include_unmatched=True)
            self.assertEqual(completed.returncode, 2)
            report = json.loads(paths["report"].read_text(encoding="utf-8"))
            self.assertFalse(report["join"]["join_complete"])
            self.assertEqual(report["join"]["n_unmatched_annotation_cells"], 1)
            self.assertEqual(report["status"], "partial_raw_count_cell_join")


if __name__ == "__main__":
    unittest.main()
