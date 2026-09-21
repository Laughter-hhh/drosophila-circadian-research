import copy
import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_public_dataset_manifest import validate_file, validate_payload


class PublicDatasetManifestTests(unittest.TestCase):
    def _payload(self):
        with (ROOT / "validation" / "public-data" / "GSE22308-provenance-manifest.json").open(encoding="utf-8") as handle:
            return json.load(handle)

    def test_real_gse22308_manifest_verifies_local_integrity(self):
        result = validate_file(
            ROOT / "validation" / "public-data" / "GSE22308-provenance-manifest.json",
            ROOT,
        )
        self.assertEqual(result["status"], "verified_public_dataset_manifest")
        self.assertEqual(result["formal_status"], "online_source_content_verified")
        manifest = self._payload()
        self.assertEqual(result["n_files"], len(manifest["files"]))
        self.assertEqual(result["n_runs"], len(manifest["runs"]))
        run_ids = {run["run_id"] for run in manifest["runs"]}
        self.assertIn("extract-gse22308-channel-regulator-expression", run_ids)
        self.assertIn("descriptive-gse22308-channel-regulator-expression-rhythm", run_ids)
        self.assertEqual(result["warnings"], [])

    def test_content_checked_requires_observation_provenance(self):
        payload = copy.deepcopy(self._payload())
        payload.pop("source_observed_tokens")
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "source_observed_tokens_must_be_nonempty_list" for issue in result["issues"]))

    def test_tampered_hash_is_blocked(self):
        payload = copy.deepcopy(self._payload())
        payload["files"][0]["sha256"] = "0" * 64
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "sha256_mismatch" for issue in result["issues"]))

    def test_unlisted_run_input_is_blocked(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0]["inputs"].append("validation/public-data/not-listed.csv")
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "run_input_not_listed_in_files" for issue in result["issues"]))

    def test_absolute_path_is_blocked(self):
        payload = copy.deepcopy(self._payload())
        payload["files"][0]["path"] = "C:/outside/file.gz"
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "file_path_must_be_safe_relative" for issue in result["issues"]))

    def test_missing_command_argv_is_blocked(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0].pop("command_argv")
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "command_argv_must_be_nonempty_string_list" for issue in result["issues"]))


    def test_parent_directory_command_argument_is_blocked(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0]["command_argv"][2] = ".."
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "command_argv_contains_unsafe_path" for issue in result["issues"]))

    def _planning_payload(self):
        payload = copy.deepcopy(self._payload())
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
        new_output = f"validation/public-data/.planning-preflight-{uuid.uuid4().hex}.json"
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
        return payload, new_output

    def test_planning_preflight_checks_inputs_and_safe_future_outputs_without_claiming_execution(self):
        payload, output_path = self._planning_payload()
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "planning_public_dataset_manifest")
        self.assertEqual(result["manifest_stage"], "planning")
        self.assertEqual(result["n_runs"], 0)
        self.assertEqual(result["n_planned_runs"], 1)
        self.assertEqual(result["planned_run_checks"][0]["status"], "planning")
        self.assertFalse(any(record["path"] == output_path for record in payload["files"]))
        self.assertFalse((ROOT / output_path).exists())

    def test_planning_output_must_be_new_and_safe(self):
        payload, _ = self._planning_payload()
        payload["planned_runs"][0]["outputs"] = ["../outside.json"]
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "planned_output_path_must_be_safe_relative" for issue in result["issues"]))

    def test_planning_stage_cannot_contain_executed_runs(self):
        payload, _ = self._planning_payload()
        payload["runs"] = [copy.deepcopy(self._payload()["runs"][0])]
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "planning_manifest_runs_must_be_empty" for issue in result["issues"]))

    def test_verified_manifest_requires_verified_run_records(self):
        payload = copy.deepcopy(self._payload())
        payload["manifest_stage"] = "verified"
        payload["runs"][0]["status"] = "executed"
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_public_dataset_manifest")
        self.assertTrue(any(issue["type"] == "verified_manifest_requires_verified_runs" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()


