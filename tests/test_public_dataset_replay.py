import copy
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import ALLOWED_SCRIPTS, _safe_argv, replay_file, replay_payload


class PublicDatasetReplayTests(unittest.TestCase):
    def _payload(self):
        with (ROOT / "validation" / "public-data" / "GSE22308-provenance-manifest.json").open(encoding="utf-8") as handle:
            return json.load(handle)

    def test_real_gse22308_replays_in_isolated_mirror(self):
        result = replay_file(
            ROOT / "validation" / "public-data" / "GSE22308-provenance-manifest.json",
            ROOT,
            timeout_seconds=120,
        )
        self.assertEqual(result["status"], "verified_public_dataset_replay")
        manifest = self._payload()
        self.assertEqual(result["n_runs"], len(manifest["runs"]))
        expected_outputs = sum(len(run["outputs"]) for run in manifest["runs"])
        self.assertEqual(result["n_output_checks"], expected_outputs)
        self.assertTrue(all(check["status"] == "replay_hash_verified" for check in result["output_checks"]))

    def test_non_python_launcher_is_rejected_before_execution(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0]["command_argv"][0] = "cmd"
        result = replay_payload(payload, ROOT, timeout_seconds=1)
        self.assertEqual(result["status"], "blocked_public_dataset_replay")
        self.assertEqual(result["runs"], [])
        self.assertTrue(any(issue["type"] == "command_argv_requires_python_launcher" for issue in result["issues"]))

    def test_valid_planning_manifest_is_never_replayed(self):
        payload = self._payload()
        source_record = next(
            record for record in payload["files"]
            if record["path"].endswith("GSE22308_candidate_expression_samples.csv")
        )
        planned = copy.deepcopy(next(
            run for run in payload["runs"]
            if run["script"] == "scripts/analyze_expression_rhythm.py"
        ))
        planned.pop("status", None)
        old_output = planned["outputs"][0]
        new_output = f"validation/public-data/.planning-replay-{uuid.uuid4().hex}.json"
        planned["outputs"] = [new_output]
        planned["command"] = planned["command"].replace(old_output, new_output)
        planned["command_argv"] = [
            new_output if item == old_output else item
            for item in planned["command_argv"]
        ]
        payload["manifest_stage"] = "planning"
        payload["files"] = [source_record]
        payload["runs"] = []
        payload["planned_runs"] = [planned]

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "planning-manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            result = replay_file(manifest_path, ROOT, timeout_seconds=1)

        self.assertEqual(result["manifest_validation"]["status"], "planning_public_dataset_manifest")
        self.assertEqual(result["status"], "blocked_public_dataset_replay")
        self.assertEqual(result["runs"], [])
        self.assertTrue(any(issue["type"] == "planning_manifest_not_replayable" for issue in result["issues"]))
        self.assertFalse((ROOT / new_output).exists())

    def test_esat_key_audit_is_allowlisted_with_safe_python_argv(self):
        script = "scripts/audit_esat_candidate_sample_keys.py"
        self.assertIn(script, ALLOWED_SCRIPTS)
        argv, issue = _safe_argv({
            "run_id": "esat-key-audit",
            "script": script,
            "command_argv": ["python", script, "--output", "validation/public-data/audit.json"],
        })
        self.assertEqual(argv, ["python", script, "--output", "validation/public-data/audit.json"])
        self.assertIsNone(issue)

    def test_esat_expression_adapter_is_allowlisted_with_safe_python_argv(self):
        script = "scripts/prepare_esat_candidate_expression.py"
        self.assertIn(script, ALLOWED_SCRIPTS)
        argv, issue = _safe_argv({
            "run_id": "esat-expression-adapter",
            "script": script,
            "command_argv": ["python", script, "--metadata", "validation/public-data/sample-map.csv"],
        })
        self.assertEqual(argv, ["python", script, "--metadata", "validation/public-data/sample-map.csv"])
        self.assertIsNone(issue)

    def test_geo_sample_map_audit_is_allowlisted_with_safe_python_argv(self):
        script = "scripts/audit_geo_sample_map.py"
        self.assertIn(script, ALLOWED_SCRIPTS)
        argv, issue = _safe_argv({
            "run_id": "geo-sample-map-audit",
            "script": script,
            "command_argv": ["python", script, "--output-report", "validation/public-data/map.json"],
        })
        self.assertEqual(argv, ["python", script, "--output-report", "validation/public-data/map.json"])
        self.assertIsNone(issue)

    def test_published_cycle_context_builder_is_allowlisted_with_safe_python_argv(self):
        script = "scripts/build_published_cycle_candidate_context.py"
        self.assertIn(script, ALLOWED_SCRIPTS)
        argv, issue = _safe_argv({
            "run_id": "published-cycle-context",
            "script": script,
            "command_argv": ["python", script, "--output-csv", "validation/public-data/context.csv"],
        })
        self.assertEqual(argv, ["python", script, "--output-csv", "validation/public-data/context.csv"])
        self.assertIsNone(issue)

    def test_design_confounding_audit_is_allowlisted_with_safe_python_argv(self):
        script = "scripts/audit_design_confounding.py"
        self.assertIn(script, ALLOWED_SCRIPTS)
        argv, issue = _safe_argv({
            "run_id": "design-confounding",
            "script": script,
            "command_argv": [
                "python", script, "metadata.csv",
                "--factor", "sex",
                "--factor", "genotype_background",
                "--output", "results/design.json",
            ],
        })
        self.assertEqual(argv, [
            "python", script, "metadata.csv",
            "--factor", "sex",
            "--factor", "genotype_background",
            "--output", "results/design.json",
        ])
        self.assertIsNone(issue)


if __name__ == "__main__":
    unittest.main()
