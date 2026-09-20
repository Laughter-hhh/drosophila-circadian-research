import copy
import json
import sys
import unittest
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
        self.assertEqual(result["n_files"], 11)
        self.assertEqual(result["n_runs"], 4)
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


if __name__ == "__main__":
    unittest.main()



