import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_gse157504_candidate_evidence import run
from scripts.replay_public_dataset_manifest import replay_file
from scripts.score_candidates import rank_rows
from scripts.validate_candidate_evidence import validate as validate_candidate_table
from scripts.validate_evidence_search_log import validate as validate_search_log
from scripts.validate_public_dataset_manifest import validate_file as validate_manifest


class GSE157504CandidateEvidenceBridgeTests(unittest.TestCase):
    def _write_csv(self, path, fields, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def _synthetic_inputs(self, root):
        candidate_path = root / "candidates.csv"
        feature_path = root / "features.csv"
        group_path = root / "groups.csv"
        rhythm_path = root / "rhythms.csv"
        self._write_csv(candidate_path, ("gene_symbol", "priority_class"), [
            {"gene_symbol": "Shab", "priority_class": "gated_Kv"},
            {"gene_symbol": "para", "priority_class": "gated_Na"},
            {"gene_symbol": "Ork1", "priority_class": "leak_K2P_like"},
        ])
        self._write_csv(feature_path, ("candidate", "priority_class", "raw_feature_status", "n_cells_detected"), [
            {"candidate": "Shab", "priority_class": "gated_Kv", "raw_feature_status": "exact_feature_present", "n_cells_detected": "9"},
            {"candidate": "para", "priority_class": "gated_Na", "raw_feature_status": "not_represented_in_raw_features_not_evaluable", "n_cells_detected": "0"},
            {"candidate": "Ork1", "priority_class": "leak_K2P_like", "raw_feature_status": "exact_feature_present", "n_cells_detected": "0"},
        ])
        self._write_csv(group_path, (
            "candidate", "priority_class", "cell_group", "condition", "time_system", "n_annotated_cells",
            "n_cells_detected", "detection_fraction",
        ), [
            {"candidate": "Shab", "priority_class": "gated_Kv", "cell_group": "s-LNv", "condition": "LD", "time_system": "ZT", "n_annotated_cells": "10", "n_cells_detected": "8", "detection_fraction": "0.8"},
            {"candidate": "Shab", "priority_class": "gated_Kv", "cell_group": "s-LNv", "condition": "DD", "time_system": "CT", "n_annotated_cells": "10", "n_cells_detected": "5", "detection_fraction": "0.5"},
            {"candidate": "Ork1", "priority_class": "leak_K2P_like", "cell_group": "s-LNv", "condition": "LD", "time_system": "ZT", "n_annotated_cells": "10", "n_cells_detected": "0", "detection_fraction": "0"},
        ])
        self._write_csv(rhythm_path, (
            "candidate", "priority_class", "condition", "cluster", "author_rhythm_class", "F24_score",
            "phase_F24_reported", "JTK_BH_q_value",
        ), [
            {"candidate": "Shab", "priority_class": "gated_Kv", "condition": "LD", "cluster": "2:s_LNv", "author_rhythm_class": "HC_cycler", "F24_score": "0.95", "phase_F24_reported": "8.2", "JTK_BH_q_value": "0.001"},
            {"candidate": "Ork1", "priority_class": "leak_K2P_like", "condition": "LD", "cluster": "9:LN_ITP", "author_rhythm_class": "HC_cycler", "F24_score": "0.8", "phase_F24_reported": "5.0", "JTK_BH_q_value": "0.01"},
        ])
        return candidate_path, feature_path, group_path, rhythm_path

    def _run(self, root, inputs, expected_hashes=None):
        outputs = (root / "evidence.csv", root / "search-log.csv", root / "report.json")
        report = run(*inputs, *outputs, root, expected_hashes, "2026-09-20")
        return outputs, report

    def test_synthetic_evidence_is_traceable_but_never_scored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._synthetic_inputs(root)
            outputs, report = self._run(root, inputs)
            evidence_path, log_path, report_path = outputs

            self.assertEqual(report["n_candidates"], 3)
            self.assertEqual(report["n_search_log_records"], 6)
            self.assertEqual(validate_search_log(log_path)["status"], "verified_evidence_search_log")
            self.assertEqual(validate_candidate_table(evidence_path, log_path)["status"], "verified_candidate_evidence_table")
            with evidence_path.open(newline="", encoding="utf-8") as handle:
                evidence = list(csv.DictReader(handle))
            by_candidate = {row["candidate"]: row for row in evidence}
            self.assertEqual(by_candidate["Shab"]["evidence_label"], "direct")
            self.assertEqual(by_candidate["Shab"]["evidence_target_cells"], "s-LNv")
            self.assertEqual(by_candidate["Shab"]["expression"], "NA")
            self.assertEqual(by_candidate["para"]["evidence_label"], "unverified")
            self.assertIn("not evidence of biological absence", by_candidate["para"]["keep_drop_reason"])
            self.assertEqual(by_candidate["Ork1"]["evidence_label"], "unverified")
            self.assertIn("LN_ITP", by_candidate["Ork1"]["evidence_notes"])
            self.assertEqual(by_candidate["Ork1"]["evidence_target_cells"], "LN_ITP_ambiguous")
            ranked = rank_rows(evidence)
            self.assertTrue(all(row["shortlist_gate"] == "needs_evidence" for row in ranked))
            self.assertTrue(all(row["score"] is None and row["coverage"] == 0 for row in ranked))
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["ranking_policy"], report["ranking_policy"])

    def test_input_hash_mismatch_blocks_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._synthetic_inputs(root)
            outputs = (root / "evidence.csv", root / "search-log.csv", root / "report.json")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                run(*inputs, *outputs, root, {"candidate_list": "0" * 64}, "2026-09-20")

    def test_condition_time_mismatch_blocks_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._synthetic_inputs(root)
            with inputs[2].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["time_system"] = "CT"
            self._write_csv(inputs[2], tuple(rows[0]), rows)
            outputs = (root / "evidence.csv", root / "search-log.csv", root / "report.json")
            with self.assertRaisesRegex(ValueError, "condition/time-system mismatch"):
                run(*inputs, *outputs, root, search_date="2026-09-20")

    def test_real_gse157504_rows_pass_both_evidence_gates_without_scores(self):
        data_dir = ROOT / "validation" / "public-data"
        manifest_path = data_dir / "GSE157504-candidate-channel-rhythm-provenance-manifest.json"
        raw_inputs = {
            "candidate_list": data_dir / "GSE22308_candidate_genes.csv",
            "feature_status": data_dir / "GSE157504_candidate_raw_feature_status.csv",
            "group_detection": data_dir / "GSE157504_candidate_raw_detection_by_group.csv",
            "rhythm_details": data_dir / "GSE157504_candidate_rhythm_details.csv",
        }
        if not manifest_path.is_file() or not all(path.is_file() for path in raw_inputs.values()):
            self.skipTest("bundled GSE157504 bridge inputs and manifest are not present")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
        expected = {
            "candidate_list": hashes["validation/public-data/GSE22308_candidate_genes.csv"],
            "feature_status": hashes["validation/public-data/GSE157504_candidate_raw_feature_status.csv"],
            "group_detection": hashes["validation/public-data/GSE157504_candidate_raw_detection_by_group.csv"],
            "rhythm_details": hashes["validation/public-data/GSE157504_candidate_rhythm_details.csv"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            outputs, report = self._run(output_root, tuple(raw_inputs.values()), expected)
            evidence_path, log_path, _ = outputs
            self.assertEqual(report["n_candidates"], 15)
            self.assertEqual(report["n_search_log_records"], 30)
            self.assertEqual(report["n_candidates_with_all_ranking_dimensions_unrated"], 15)
            self.assertEqual(validate_search_log(log_path)["status"], "verified_evidence_search_log")
            self.assertEqual(validate_candidate_table(evidence_path, log_path)["status"], "verified_candidate_evidence_table")
            with evidence_path.open(newline="", encoding="utf-8") as handle:
                evidence = list(csv.DictReader(handle))
            self.assertTrue(all(row[field] == "NA" for row in evidence for field in (
                "expression", "electrophysiology", "genetic_tools", "class_match", "rhythmic_evidence", "fly_causal", "cross_species"
            )))
            self.assertEqual(sum(row["candidate"] == "Shab" and row["evidence_label"] == "direct" for row in evidence), 1)
            self.assertTrue(all(row["shortlist_gate"] == "needs_evidence" for row in rank_rows(evidence)))

    def test_checked_in_bridge_manifest_is_verified_and_replayable(self):
        manifest = ROOT / "validation" / "public-data" / "GSE157504-candidate-evidence-bridge-manifest.json"
        validation = validate_manifest(manifest, ROOT)
        self.assertEqual(validation["status"], "verified_public_dataset_manifest", validation.get("issues"))
        self.assertEqual(validation["manifest_stage"], "verified")
        self.assertEqual(validation["n_runs"], 4)
        replay = replay_file(manifest, ROOT, timeout_seconds=180)
        self.assertEqual(replay["status"], "verified_public_dataset_replay", replay.get("issues"))
        self.assertEqual(replay["n_runs"], 4)
        self.assertEqual(replay["n_output_checks"], 7)
        report = json.loads((ROOT / "validation/public-data/GSE157504_candidate_evidence_handoff_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["n_candidates_with_all_ranking_dimensions_unrated"], 15)
        score_path = ROOT / "validation/public-data/GSE157504_candidate_evidence_score_diagnostic.csv"
        with score_path.open(newline="", encoding="utf-8") as handle:
            score_rows = list(csv.DictReader(handle))
        self.assertTrue(score_rows)
        self.assertTrue(all(row["shortlist_gate"] == "needs_evidence" for row in score_rows))


if __name__ == "__main__":
    unittest.main()
