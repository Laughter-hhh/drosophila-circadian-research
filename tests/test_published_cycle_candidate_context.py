import argparse
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_published_cycle_candidate_context import (
    ADDED_FIELDS,
    CYCLE_REQUIRED,
    SOURCE_GROUPS,
    _sha256,
    _validate_outputs,
    _verify_parent_bundle,
    _validate_cycle_audit,
    build_context_rows,
    run,
)
from scripts.replay_public_dataset_manifest import replay_file
from scripts.validate_public_dataset_manifest import validate_file


def _synthetic_audit():
    candidates = {
        "Shab": {
            SOURCE_GROUPS[0]: [{"cycle_class": "HC", "source_row": 8}],
            SOURCE_GROUPS[1]: [],
            SOURCE_GROUPS[2]: [{"cycle_class": "LC", "source_row": 20}],
        },
        "Sh": {
            SOURCE_GROUPS[0]: [],
            SOURCE_GROUPS[1]: [{"cycle_class": "LC", "source_row": 7}],
            SOURCE_GROUPS[2]: [],
        },
        "ListedButNotCycling": {group: [] for group in SOURCE_GROUPS},
    }
    audit = {
        "matching": {
            "candidate_count": len(candidates),
            "target_group_count": len(SOURCE_GROUPS),
            "candidate_group_rows": len(candidates) * len(SOURCE_GROUPS),
        },
        "candidate_summary": [
            {"candidate_symbol": gene, "by_group": by_group}
            for gene, by_group in candidates.items()
        ],
    }
    rows = []
    for gene, by_group in candidates.items():
        for group, calls in by_group.items():
            note = {
                SOURCE_GROUPS[0]: "Pooled positive LNv source group; no s-/l-LNv resolution.",
                SOURCE_GROUPS[1]: "LNd source group includes fifth PDF-negative s-LNv.",
                SOURCE_GROUPS[2]: "DN1 subset source group.",
            }[group]
            if not calls:
                rows.append({
                    "candidate_symbol": gene,
                    "cell_group": group,
                    "source_row": "",
                    "source_list_status": "not_listed_in_published_cycler_supplement",
                    "published_cycle_class": "not_listed",
                    "author_F24_flag": "",
                    "author_JTK_flag": "",
                    "cell_group_scope_note": note,
                })
            else:
                for call in calls:
                    is_hc = call["cycle_class"] == "HC"
                    rows.append({
                        "candidate_symbol": gene,
                        "cell_group": group,
                        "source_row": str(call["source_row"]),
                        "source_list_status": "listed_as_published_cycler",
                        "published_cycle_class": call["cycle_class"],
                        "author_F24_flag": "True",
                        "author_JTK_flag": str(is_hc).title(),
                        "cell_group_scope_note": note,
                    })
    return audit, rows


class PublishedCycleCandidateContextTests(unittest.TestCase):
    def test_target_scope_and_missingness_are_separate_and_scores_stay_unchanged(self):
        audit, rows = _synthetic_audit()
        cycle_index, candidates, shape = _validate_cycle_audit(rows, audit)
        base_fields = [
            "candidate", "target_group", "literature_score", "ephys_directness_gate",
            "shortlist_gate", "scoring_readout_match",
        ]
        base = [
            {"candidate": "Shab", "target_group": "s-LNv", "literature_score": "2.5", "ephys_directness_gate": "pass", "shortlist_gate": "pass", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "Shab", "target_group": "l-LNv", "literature_score": "2.5", "ephys_directness_gate": "pass", "shortlist_gate": "pass", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "Shab", "target_group": "DN", "literature_score": "2.5", "ephys_directness_gate": "pass", "shortlist_gate": "pass", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "Sh", "target_group": "LNd", "literature_score": "1.5", "ephys_directness_gate": "needs_evidence", "shortlist_gate": "needs_evidence", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "ListedButNotCycling", "target_group": "s-LNv", "literature_score": "0.5", "ephys_directness_gate": "needs_evidence", "shortlist_gate": "needs_evidence", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "NotInAudit", "target_group": "s-LNv", "literature_score": "0", "ephys_directness_gate": "needs_evidence", "shortlist_gate": "needs_evidence", "scoring_readout_match": "membrane_potential_or_current"},
            {"candidate": "Sh", "target_group": "DN1p", "literature_score": "1.5", "ephys_directness_gate": "needs_evidence", "shortlist_gate": "needs_evidence", "scoring_readout_match": "membrane_potential_or_current"},
        ]

        enriched = build_context_rows(base, base_fields, cycle_index, candidates, shape["source_scope_notes"])
        by_key = {(row["candidate"], row["target_group"]): row for row in enriched}
        self.assertEqual(len(enriched), len(base))
        self.assertEqual(set(by_key), {(row["candidate"], row["target_group"]) for row in base})
        for source, output in zip(base, enriched, strict=True):
            self.assertEqual({field: source[field] for field in base_fields}, {field: output[field] for field in base_fields})
        self.assertTrue(set(ADDED_FIELDS).issubset(enriched[0]))

        slnv = by_key[("Shab", "s-LNv")]
        llnv = by_key[("Shab", "l-LNv")]
        self.assertEqual(slnv["published_cycle_author_class"], "HC")
        self.assertEqual(llnv["published_cycle_author_class"], "HC")
        self.assertEqual(slnv["published_cycle_source_group"], llnv["published_cycle_source_group"])
        self.assertEqual(slnv["published_cycle_target_scope_relation"], "pooled_LNv_does_not_resolve_s_LNv")
        self.assertEqual(llnv["published_cycle_target_scope_relation"], "pooled_LNv_does_not_resolve_l_LNv")
        self.assertEqual(by_key[("Shab", "DN")]["published_cycle_author_class"], "LC")
        self.assertEqual(by_key[("Shab", "DN")]["published_cycle_target_scope_relation"], "DN1_subset_not_all_dorsal_neurons")
        self.assertEqual(by_key[("Sh", "LNd")]["published_cycle_author_class"], "LC")
        self.assertIn("fifth PDF-negative s-LNv", by_key[("Sh", "LNd")]["published_cycle_source_scope_note"])
        self.assertEqual(by_key[("ListedButNotCycling", "s-LNv")]["published_cycle_record_status"], "not_listed_in_published_cycler_supplement")
        self.assertEqual(by_key[("ListedButNotCycling", "s-LNv")]["published_cycle_author_class"], "not_listed")
        self.assertEqual(by_key[("NotInAudit", "s-LNv")]["published_cycle_record_status"], "candidate_not_in_published_cycle_audit_not_evaluable")
        self.assertEqual(by_key[("NotInAudit", "s-LNv")]["published_cycle_author_class"], "not_evaluable")
        self.assertEqual(by_key[("Sh", "DN1p")]["published_cycle_record_status"], "source_group_not_mapped")

    def test_conflicting_source_rows_are_preserved_as_conflict_not_collapsed(self):
        audit, rows = _synthetic_audit()
        by_candidate = next(item for item in audit["candidate_summary"] if item["candidate_symbol"] == "Shab")
        by_candidate["by_group"][SOURCE_GROUPS[0]].append({"cycle_class": "LC", "source_row": 9})
        duplicate = dict(next(row for row in rows if row["candidate_symbol"] == "Shab" and row["cell_group"] == SOURCE_GROUPS[0]))
        duplicate.update({
            "source_row": "9",
            "published_cycle_class": "LC",
            "author_F24_flag": "True",
            "author_JTK_flag": "False",
        })
        rows.append(duplicate)
        cycle_index, candidates, shape = _validate_cycle_audit(rows, audit)
        result = build_context_rows(
            [{"candidate": "Shab", "target_group": "s-LNv", "literature_score": "3"}],
            ["candidate", "target_group", "literature_score"],
            cycle_index,
            candidates,
            shape["source_scope_notes"],
        )[0]
        self.assertEqual(result["published_cycle_record_status"], "conflicting_published_cycle_source_records")
        self.assertEqual(result["published_cycle_author_class"], "conflict")
        self.assertEqual(json.loads(result["published_cycle_source_rows_json"]), [8, 9])

    def test_duplicate_base_candidate_target_keys_fail_closed(self):
        audit, rows = _synthetic_audit()
        cycle_index, candidates, shape = _validate_cycle_audit(rows, audit)
        base = {"candidate": "Shab", "target_group": "s-LNv", "literature_score": "3"}
        with self.assertRaisesRegex(ValueError, "duplicate candidate/target key"):
            build_context_rows(
                [base, dict(base)],
                ["candidate", "target_group", "literature_score"],
                cycle_index,
                candidates,
                shape["source_scope_notes"],
            )

    def test_audit_report_mismatch_and_flag_class_disagreement_fail_closed(self):
        audit, rows = _synthetic_audit()
        rows[0]["author_JTK_flag"] = "False"
        with self.assertRaisesRegex(ValueError, "flags disagree"):
            _validate_cycle_audit(rows, audit)

        audit, rows = _synthetic_audit()
        rows.pop()
        with self.assertRaisesRegex(ValueError, "evidence rows disagree|missing or inconsistent"):
            _validate_cycle_audit(rows, audit)

    def test_unverified_parent_replay_and_output_input_collision_are_blocked(self):
        with tempfile.TemporaryDirectory(prefix=".tmp-parent-gate-", dir=ROOT) as tmp:
            temp_root = Path(tmp)
            output = temp_root / "parent-output.csv"
            output.write_text("gene\\nShab\\n", encoding="utf-8")
            output_rel = output.relative_to(temp_root).as_posix()
            digest = _sha256(output)
            manifest_path = temp_root / "parent-manifest.json"
            validation_path = temp_root / "parent-validation.json"
            replay_path = temp_root / "parent-replay.json"
            manifest_path.write_text(json.dumps({
                "manifest_id": "parent-test",
                "files": [{"path": output_rel, "role": "derived", "sha256": digest}],
            }), encoding="utf-8")
            validation_path.write_text(json.dumps({
                "manifest_id": "parent-test",
                "status": "verified_public_dataset_manifest",
                "file_checks": [{"path": output_rel, "status": "hash_verified", "observed_sha256": digest}],
            }), encoding="utf-8")
            replay_path.write_text(json.dumps({"status": "blocked_public_dataset_replay"}), encoding="utf-8")
            with patch("scripts.build_published_cycle_candidate_context.validate_file", return_value={
                "manifest_id": "parent-test",
                "status": "verified_public_dataset_manifest",
                "file_checks": [{"path": output_rel, "status": "hash_verified", "observed_sha256": digest}],
            }):
                with self.assertRaisesRegex(ValueError, "isolated replay is not verified"):
                    _verify_parent_bundle(
                        "synthetic parent", manifest_path, validation_path, replay_path,
                        (output_rel,), temp_root,
                    )

        existing_input = ROOT / "validation/public-data/GSE157504_candidate_context_overlay.csv"
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            _validate_outputs(
                (existing_input, ROOT / "validation/public-data/temp-report.json", ROOT / "validation/public-data/temp-manifest.json"),
                [existing_input],
                ROOT,
            )

    def test_real_public_parents_join_without_modifying_context_and_replay(self):
        source = {
            "gse_context": "validation/public-data/GSE157504_candidate_context_overlay.csv",
            "gse_report": "validation/public-data/GSE157504_candidate_context_overlay_report.json",
            "gse_manifest": "validation/public-data/GSE157504-candidate-context-overlay-manifest.json",
            "gse_validation": "validation/public-data/GSE157504-candidate-context-overlay-manifest-validation.json",
            "gse_replay": "validation/public-data/GSE157504-candidate-context-overlay-replay.json",
            "cycle_evidence": "validation/public-data/Abruzzi2017_channel-candidate-cycle-evidence.csv",
            "cycle_report": "validation/public-data/Abruzzi2017_channel-candidate-cycle-audit.json",
            "cycle_manifest": "validation/public-data/Abruzzi2017-candidate-cycle-manifest.json",
            "cycle_validation": "validation/public-data/Abruzzi2017-candidate-cycle-manifest-validation.json",
            "cycle_replay": "validation/public-data/Abruzzi2017-candidate-cycle-replay.json",
        }
        with tempfile.TemporaryDirectory(prefix=".tmp-combined-cycle-context-", dir=ROOT) as tmp:
            temp_root = Path(tmp)
            rel = lambda name: (temp_root / name).relative_to(ROOT).as_posix()
            output_csv = rel("context.csv")
            output_report = rel("report.json")
            output_manifest = rel("manifest.json")
            args = argparse.Namespace(
                root=ROOT,
                **{key: Path(value) for key, value in source.items()},
                output_csv=Path(output_csv),
                output_report=Path(output_report),
                manifest_output=Path(output_manifest),
            )
            argv = []
            for key, value in source.items():
                option = {
                    "gse_context": "--gse-context", "gse_report": "--gse-report",
                    "gse_manifest": "--gse-manifest", "gse_validation": "--gse-validation",
                    "gse_replay": "--gse-replay", "cycle_evidence": "--cycle-evidence",
                    "cycle_report": "--cycle-report", "cycle_manifest": "--cycle-manifest",
                    "cycle_validation": "--cycle-validation", "cycle_replay": "--cycle-replay",
                }[key]
                argv.extend([option, value])
            argv.extend([
                "--output-csv", output_csv,
                "--output-report", output_report,
                "--manifest-output", output_manifest,
            ])
            report = run(args, argv)
            self.assertEqual(report["status"], "executed_published_cycle_candidate_context_overlay")
            self.assertEqual(report["n_input_context_rows"], 60)
            self.assertEqual(report["n_output_rows"], 60)
            self.assertEqual(report["candidate_set_difference"]["gse_context_candidates_not_in_published_cycle_audit"], [])
            self.assertEqual(report["candidate_set_difference"]["published_cycle_audit_candidates_not_in_gse_context"], [])
            self.assertEqual(report["n_listed_HC_target_rows"], 2)
            self.assertEqual(report["n_listed_LC_target_rows"], 7)
            self.assertEqual(report["n_not_listed_target_rows"], 51)
            self.assertEqual(report["distinct_published_source_calls"]["candidate_group_pairs"], 6)
            self.assertEqual(report["distinct_published_source_calls"]["source_records"], 6)
            self.assertEqual(report["distinct_published_source_calls"]["HC_candidate_group_pairs"], 1)
            self.assertEqual(report["distinct_published_source_calls"]["LC_candidate_group_pairs"], 5)
            self.assertTrue(report["score_and_gate_invariants"]["all_input_context_values_copied_verbatim"])
            self.assertFalse(report["score_and_gate_invariants"]["scores_recomputed"])
            self.assertFalse(report["score_and_gate_invariants"]["ephys_gate_recomputed"])
            discrepancy = report["parent_published_cycle_audit"]["source_discrepancies"]
            self.assertEqual(len(discrepancy), 1)
            self.assertEqual(discrepancy[0]["paper_reported_HC_n"], 249)
            self.assertEqual(discrepancy[0]["supplement_unique_symbol_HC_count"], 252)

            with (ROOT / source["gse_context"]).open(newline="", encoding="utf-8") as handle:
                original_reader = csv.DictReader(handle)
                original_fields = list(original_reader.fieldnames or [])
                original_rows = list(original_reader)
            with (ROOT / output_csv).open(newline="", encoding="utf-8") as handle:
                joined_rows = list(csv.DictReader(handle))
            self.assertEqual(len(joined_rows), len(original_rows))
            for original, joined in zip(original_rows, joined_rows, strict=True):
                self.assertEqual({field: original[field] for field in original_fields}, {field: joined[field] for field in original_fields})
            lookup = {(row["candidate"], row["target_group"]): row for row in joined_rows}
            self.assertEqual(lookup[("Shab", "s-LNv")]["published_cycle_author_class"], "HC")
            self.assertEqual(lookup[("Shab", "l-LNv")]["published_cycle_author_class"], "HC")
            self.assertEqual(lookup[("Shab", "DN")]["published_cycle_author_class"], "LC")
            self.assertEqual(lookup[("Sh", "LNd")]["published_cycle_author_class"], "LC")
            self.assertEqual(lookup[("Shaw", "s-LNv")]["published_cycle_record_status"], "not_listed_in_published_cycler_supplement")
            self.assertEqual(lookup[("na", "s-LNv")]["published_cycle_record_status"], "not_listed_in_published_cycler_supplement")
            self.assertEqual(lookup[("na", "s-LNv")]["raw_feature_status"], "candidate_not_in_upstream_audit_not_evaluable")

            manifest_path = ROOT / output_manifest
            validation = validate_file(manifest_path, ROOT)
            self.assertEqual(validation["status"], "verified_public_dataset_manifest", validation.get("issues"))
            replay = replay_file(manifest_path, ROOT, timeout_seconds=180)
            self.assertEqual(replay["status"], "verified_public_dataset_replay", replay.get("issues"))
            self.assertEqual(len(replay["output_checks"]), 2)
            self.assertTrue(all(check["status"] == "replay_hash_verified" for check in replay["output_checks"]))


if __name__ == "__main__":
    unittest.main()
