import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_gse157504_candidate_detection import run


class GSE157504DetectionPublicApiTests(unittest.TestCase):
    def test_real_public_dataset_join_is_hash_checked_through_import_api(self):
        data_dir = ROOT / "validation" / "public-data"
        manifest_path = data_dir / "GSE157504-candidate-channel-rhythm-provenance-manifest.json"
        raw_tar = data_dir / "GSE157504_RAW.tar"
        annotation = data_dir / "GSE157504_clock_neurons_annotation.csv"
        candidates = data_dir / "GSE22308_candidate_genes.csv"
        required = (manifest_path, raw_tar, annotation, candidates)
        if not all(path.is_file() for path in required):
            self.skipTest("bundled GSE157504 public data and manifest are not present")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
        expected_hashes = {
            "raw_counts": hashes["validation/public-data/GSE157504_RAW.tar"],
            "annotation": hashes["validation/public-data/GSE157504_clock_neurons_annotation.csv"],
            "candidate_list": hashes["validation/public-data/GSE22308_candidate_genes.csv"],
        }
        sample_rows, group_rows, feature_rows, report = run(
            raw_tar, annotation, candidates, ROOT, expected_hashes
        )

        self.assertTrue(report["join"]["join_complete"])
        self.assertEqual(report["join"]["n_annotation_cells"], 2615)
        self.assertEqual(report["join"]["n_unique_annotated_cells_matched_once"], 2615)
        self.assertEqual(report["join"]["n_raw_matrix_members"], 84)
        self.assertEqual(report["join"]["n_unannotated_raw_columns"], 5445)
        self.assertEqual(report["annotation_time_grid"]["missing_replicate_timepoints"], [])
        self.assertGreater(len(sample_rows), 0)

        exact_features = [row for row in feature_rows if row["raw_feature_status"] == "exact_feature_present"]
        self.assertEqual(len(exact_features), 14)
        by_candidate = {row["candidate"]: row for row in feature_rows}
        self.assertEqual(by_candidate["para"]["raw_feature_status"], "not_represented_in_raw_features_not_evaluable")

        by_group = {(row["candidate"], row["cell_group"], row["condition"]): row for row in group_rows}
        self.assertEqual(by_group[("Shab", "s-LNv", "LD")]["n_cells_detected"], "160")
        self.assertEqual(by_group[("Shab", "s-LNv", "DD")]["n_cells_detected"], "97")
        self.assertEqual(by_group[("Shab", "s-LNv", "LD")]["time_system"], "ZT")
        self.assertEqual(by_group[("Shab", "s-LNv", "DD")]["time_system"], "CT")


if __name__ == "__main__":
    unittest.main()
