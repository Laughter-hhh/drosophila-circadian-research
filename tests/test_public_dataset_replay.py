import copy
import json
import sys
import unittest
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
        self.assertEqual(result["n_runs"], 5)
        self.assertEqual(result["n_output_checks"], 7)
        self.assertTrue(all(check["status"] == "replay_hash_verified" for check in result["output_checks"]))

    def test_non_python_launcher_is_rejected_before_execution(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0]["command_argv"][0] = "cmd"
        result = replay_payload(payload, ROOT, timeout_seconds=1)
        self.assertEqual(result["status"], "blocked_public_dataset_replay")
        self.assertEqual(result["runs"], [])
        self.assertTrue(any(issue["type"] == "command_argv_requires_python_launcher" for issue in result["issues"]))

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


if __name__ == "__main__":
    unittest.main()
