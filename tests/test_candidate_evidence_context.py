import argparse
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_candidate_evidence_context import TARGET_GROUPS, _validate_output_paths, build_context_rows, run
from scripts.score_candidates import score_row
from scripts.validate_public_dataset_manifest import validate_file as validate_manifest


def _candidate(gene, reason=""):
    return {
        "candidate": gene,
        "class": "leak_Kir",
        "organism": "Drosophila melanogaster",
        "target_cell_scope": "indirect_or_unverified",
        "evidence_target_cells": "unverified",
        "assay": "FlyBase gene report",
        "readout_match": "none_or_unverified",
        "evidence_label": "unverified",
        "expression": "NA",
        "electrophysiology": "NA",
        "genetic_tools": "1",
        "class_match": "2",
        "rhythmic_evidence": "NA",
        "fly_causal": "NA",
        "cross_species": "NA",
        "keep_drop_reason": reason or "retain conditionally; evidence is incomplete",
        "sources": "https://flybase.org/",
        "confidence": "low",
        "evidence_notes": "Synthetic fixture only.",
    }


def _synthetic_inputs():
    candidates = [
        _candidate("Chan", "deprioritize: target-neuron and circadian evidence are missing"),
        _candidate("para"),
        _candidate("outside"),
    ]
    features = [
        {"candidate": "Chan", "priority_class": "gated_Kv", "raw_feature_status": "exact_feature_present", "n_cells_detected": "12"},
        {"candidate": "para", "priority_class": "gated_Na", "raw_feature_status": "not_represented_in_raw_features_not_evaluable", "n_cells_detected": "0"},
        {"candidate": "eag", "priority_class": "gated_Kv", "raw_feature_status": "exact_feature_present", "n_cells_detected": "4"},
    ]
    groups = []
    for target in TARGET_GROUPS:
        for condition, time_system in (("LD", "ZT"), ("DD", "CT")):
            detected = 0 if target == "s-LNv" and condition == "LD" else 2
            groups.append({
                "candidate": "Chan", "priority_class": "gated_Kv", "cell_group": target,
                "condition": condition, "time_system": time_system, "n_annotated_cells": "10",
                "n_cells_detected": str(detected), "detection_fraction": str(detected / 10),
                "sum_raw_counts": str(detected * 2), "mean_raw_counts_per_cell": str(detected * 0.2),
            })
    rhythms = [
        {"candidate": "Chan", "priority_class": "gated_Kv", "condition": "DD", "cluster": "2:s_LNv", "author_rhythm_class": "HC_cycler", "F24_score": "0.9", "phase_F24_reported": "7.5", "JTK_BH_q_value": "0.001"},
        {"candidate": "Chan", "priority_class": "gated_Kv", "condition": "LD", "cluster": "8:LN_ITP", "author_rhythm_class": "HC_cycler", "F24_score": "0.8", "phase_F24_reported": "5.0", "JTK_BH_q_value": "0.01"},
        {"candidate": "Chan", "priority_class": "gated_Kv", "condition": "LD", "cluster": "4:DN1p", "author_rhythm_class": "HC_cycler", "F24_score": "0.7", "phase_F24_reported": "4.5", "JTK_BH_q_value": "0.02"},
    ]
    target_scores = {
        target: {
            row["candidate"]: score_row(row, target_cells=[target], evidence_log=[], readout_match="membrane_potential_or_current")
            for row in candidates
        }
        for target in TARGET_GROUPS
    }
    return candidates, features, groups, rhythms, target_scores


class CandidateEvidenceContextTests(unittest.TestCase):
    def test_synthetic_context_preserves_uncertainty_scope_and_score_gate(self):
        candidates, features, groups, rhythms, scores = _synthetic_inputs()
        rows = build_context_rows(candidates, features, groups, rhythms, scores, [])
        self.assertEqual(len(rows), 12)
        by_key = {(row["candidate"], row["target_group"]): row for row in rows}

        slnv = by_key[("Chan", "s-LNv")]
        self.assertEqual(slnv["LD_detection_status"], "zero_UMI_dropout_sensitive_not_absent")
        self.assertEqual(slnv["DD_detection_status"], "raw_UMI_detected_descriptive_only")
        self.assertEqual(slnv["target_author_rhythm_status"], "HC_call_listed_in_target_group")
        self.assertEqual(json.loads(slnv["target_author_rhythm_calls"])[0]["time_system"], "CT")
        self.assertEqual(json.loads(slnv["target_author_rhythm_calls"])[0]["mapped_group"], "s-LNv")
        self.assertEqual(json.loads(slnv["ambiguous_LN_ITP_rhythm_calls"])[0]["mapped_group"], "LN_ITP_ambiguous")
        self.assertEqual(slnv["static_rationale_review_flag"], "review")
        self.assertEqual(slnv["literature_score"], scores["s-LNv"]["Chan"]["score"])
        self.assertEqual(slnv["ephys_directness_gate"], scores["s-LNv"]["Chan"]["directness_gate"])

        lnd = by_key[("Chan", "LNd")]
        self.assertEqual(lnd["target_author_rhythm_status"], "not_listed_under_author_HC_criteria_not_proven_arrhythmic")
        self.assertEqual(json.loads(lnd["ambiguous_LN_ITP_rhythm_calls"])[0]["mapped_group"], "LN_ITP_ambiguous")
        dn = by_key[("Chan", "DN")]
        dn_call = json.loads(dn["target_author_rhythm_calls"])[0]
        self.assertEqual(dn_call["cluster"], "4:DN1p")
        self.assertIn("not evidence for all DN", dn["DN_subcluster_scope_note"])

        para = by_key[("para", "s-LNv")]
        self.assertEqual(para["transcript_evaluable"], "no")
        self.assertEqual(para["LD_n_cells_detected"], "NA")
        self.assertIn("not_evaluable", para["LD_detection_status"])
        outside = by_key[("outside", "s-LNv")]
        self.assertEqual(outside["raw_feature_status"], "candidate_not_in_upstream_audit_not_evaluable")
        self.assertEqual(outside["target_author_rhythm_status"], "candidate_not_in_upstream_audit_rhythm_status_not_evaluable")
        self.assertEqual(outside["target_author_rhythm_calls"], "NA")

    def test_duplicate_and_condition_time_mismatch_fail_closed(self):
        candidates, features, groups, rhythms, scores = _synthetic_inputs()
        with self.assertRaisesRegex(ValueError, "duplicate group-detection"):
            build_context_rows(candidates, features, groups + [groups[0]], rhythms, scores, [])
        bad_groups = [dict(row) for row in groups]
        bad_groups[0]["time_system"] = "CT"
        with self.assertRaisesRegex(ValueError, "condition/time-system mismatch"):
            build_context_rows(candidates, features, bad_groups, rhythms, scores, [])

    def test_zero_annotated_cells_keep_undefined_fraction_and_mean_as_na(self):
        candidates, features, groups, rhythms, scores = _synthetic_inputs()
        adjusted = [dict(row) for row in groups]
        row = next(item for item in adjusted if item["cell_group"] == "l-LNv" and item["condition"] == "LD")
        row.update({
            "n_annotated_cells": "0", "n_cells_detected": "0", "detection_fraction": "",
            "sum_raw_counts": "0", "mean_raw_counts_per_cell": "",
        })
        output = build_context_rows(candidates, features, adjusted, rhythms, scores, [])
        llnv = next(item for item in output if item["candidate"] == "Chan" and item["target_group"] == "l-LNv")
        self.assertEqual(llnv["LD_detection_status"], "no_annotated_cells_no_detection_inference")
        self.assertEqual(llnv["LD_n_annotated_cells"], 0)
        self.assertEqual(llnv["LD_detection_fraction"], "NA")
        self.assertEqual(llnv["LD_mean_raw_counts_per_cell"], "NA")

    def test_output_collision_guard_preserves_all_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.csv"
            source.write_text("keep me\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overwrite an input"):
                _validate_output_paths((source, root / "report.json", root / "manifest.json"), [source], root)
            with self.assertRaisesRegex(ValueError, "distinct paths"):
                _validate_output_paths((root / "same", root / "same", root / "manifest"), [], root)

    def test_real_public_inputs_generate_auditable_sixty_row_overlay(self):
        data = ROOT / "validation" / "public-data"
        names = {
            "candidate_table": "candidate-evidence-real.csv",
            "search_log": "candidate-evidence-search-log.csv",
            "feature_status": "GSE157504_candidate_raw_feature_status.csv",
            "group_detection": "GSE157504_candidate_raw_detection_by_group.csv",
            "rhythm_details": "GSE157504_candidate_rhythm_details.csv",
            "rhythm_manifest": "GSE157504-candidate-channel-rhythm-provenance-manifest.json",
            "rhythm_validation": "GSE157504-candidate-channel-rhythm-manifest-validation.json",
            "rhythm_replay": "GSE157504-candidate-channel-rhythm-replay.json",
        }
        inputs = {key: data / value for key, value in names.items()}
        target_files = {
            "s-LNv": "candidate-target-cell-score-slnv.csv",
            "l-LNv": "candidate-target-cell-score-llnv.csv",
            "LNd": "candidate-target-cell-score-lnd.csv",
            "DN": "candidate-target-cell-score-dn.csv",
        }
        if not all(path.is_file() for path in (*inputs.values(), *(data / p for p in target_files.values()))):
            self.skipTest("bundled candidate/GSE157504 inputs are not present")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="candidate-context-test-") as temporary:
            tmp = Path(temporary).relative_to(ROOT).as_posix()
            args = argparse.Namespace(
                root=ROOT,
                candidate_table=Path("validation/public-data/candidate-evidence-real.csv"),
                search_log=Path("validation/public-data/candidate-evidence-search-log.csv"),
                feature_status=Path("validation/public-data/GSE157504_candidate_raw_feature_status.csv"),
                group_detection=Path("validation/public-data/GSE157504_candidate_raw_detection_by_group.csv"),
                rhythm_details=Path("validation/public-data/GSE157504_candidate_rhythm_details.csv"),
                rhythm_manifest=Path("validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json"),
                rhythm_validation=Path("validation/public-data/GSE157504-candidate-channel-rhythm-manifest-validation.json"),
                rhythm_replay=Path("validation/public-data/GSE157504-candidate-channel-rhythm-replay.json"),
                target_score=[(target, Path(f"validation/public-data/{filename}")) for target, filename in target_files.items()],
                context_output=Path(f"{tmp}/context.csv"),
                report_output=Path(f"{tmp}/report.json"),
                manifest_output=Path(f"{tmp}/manifest.json"),
            )
            raw_argv = [
                "--candidate-table", "validation/public-data/candidate-evidence-real.csv",
                "--search-log", "validation/public-data/candidate-evidence-search-log.csv",
                "--feature-status", "validation/public-data/GSE157504_candidate_raw_feature_status.csv",
                "--group-detection", "validation/public-data/GSE157504_candidate_raw_detection_by_group.csv",
                "--rhythm-details", "validation/public-data/GSE157504_candidate_rhythm_details.csv",
                "--rhythm-manifest", "validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json",
                "--rhythm-validation", "validation/public-data/GSE157504-candidate-channel-rhythm-manifest-validation.json",
                "--rhythm-replay", "validation/public-data/GSE157504-candidate-channel-rhythm-replay.json",
            ]
            for target, filename in target_files.items():
                raw_argv.extend(("--target-score", f"{target}=validation/public-data/{filename}"))
            raw_argv.extend(("--context-output", f"{tmp}/context.csv", "--report-output", f"{tmp}/report.json", "--manifest-output", f"{tmp}/manifest.json"))
            report = run(args, raw_argv)
            context_path = ROOT / tmp / "context.csv"
            with context_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_key = {(row["candidate"], row["target_group"]): row for row in rows}
            self.assertEqual(report["n_rows"], 60)
            self.assertEqual(report["candidate_set_difference"]["literature_candidates_not_in_GSE_candidate_audit"], ["na"])
            self.assertEqual(report["candidate_set_difference"]["GSE_candidates_not_in_literature_table"], ["eag"])
            self.assertEqual(by_key[("Shab", "s-LNv")]["LD_n_cells_detected"], "160")
            self.assertEqual(by_key[("Shab", "s-LNv")]["DD_n_cells_detected"], "97")
            self.assertEqual(by_key[("Shab", "s-LNv")]["static_rationale_review_flag"], "review")
            self.assertEqual(by_key[("Shab", "s-LNv")]["ephys_directness_gate"], "needs_direct_evidence")
            self.assertEqual(by_key[("na", "s-LNv")]["raw_feature_status"], "candidate_not_in_upstream_audit_not_evaluable")
            self.assertEqual(by_key[("na", "s-LNv")]["target_author_rhythm_status"], "candidate_not_in_upstream_audit_rhythm_status_not_evaluable")
            self.assertEqual(by_key[("para", "s-LNv")]["LD_n_cells_detected"], "NA")
            validation = validate_manifest(ROOT / tmp / "manifest.json", ROOT)
            self.assertEqual(validation["status"], "verified_public_dataset_manifest")

            protected_bytes = inputs["candidate_table"].read_bytes()
            collision_args = argparse.Namespace(**vars(args))
            collision_args.context_output = Path("validation/public-data/candidate-evidence-real.csv")
            collision_args.report_output = Path(f"{tmp}/collision-report.json")
            collision_args.manifest_output = Path(f"{tmp}/collision-manifest.json")
            with self.assertRaisesRegex(ValueError, "overwrite an input"):
                run(collision_args, raw_argv)
            self.assertEqual(inputs["candidate_table"].read_bytes(), protected_bytes)


if __name__ == "__main__":
    unittest.main()
