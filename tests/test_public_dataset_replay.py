import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import replay_file, replay_payload


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
        self.assertEqual(result["n_runs"], 4)
        self.assertEqual(result["n_output_checks"], 6)
        self.assertTrue(all(check["status"] == "replay_hash_verified" for check in result["output_checks"]))

    def test_non_python_launcher_is_rejected_before_execution(self):
        payload = copy.deepcopy(self._payload())
        payload["runs"][0]["command_argv"][0] = "cmd"
        result = replay_payload(payload, ROOT, timeout_seconds=1)
        self.assertEqual(result["status"], "blocked_public_dataset_replay")
        self.assertEqual(result["runs"], [])
        self.assertTrue(any(issue["type"] == "command_argv_requires_python_launcher" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()

