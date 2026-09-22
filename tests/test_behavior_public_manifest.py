import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import replay_file
from scripts.validate_public_dataset_manifest import validate_file


MANIFEST = ROOT / "validation" / "public-data" / "zenodo-18214640-metadata-provenance-manifest.json"


class BehaviorPublicManifestTests(unittest.TestCase):
    def test_real_zenodo_manifest_verifies(self):
        result = validate_file(MANIFEST, ROOT)
        self.assertEqual(result["status"], "verified_public_dataset_manifest")
        self.assertEqual(result["manifest_stage"], "verified")
        self.assertEqual(result["formal_status"], "online_source_content_verified")
        self.assertEqual(result["n_files"], 2)
        self.assertEqual(result["n_runs"], 1)

    def test_real_zenodo_manifest_replays_in_isolated_mirror(self):
        result = replay_file(MANIFEST, ROOT, timeout_seconds=120)
        self.assertEqual(result["status"], "verified_public_dataset_replay")
        self.assertEqual(result["n_runs"], 1)
        self.assertEqual(result["n_output_checks"], 1)
        self.assertEqual(result["output_checks"][0]["status"], "replay_hash_verified")
        self.assertEqual(result["manifest_validation"]["manifest_stage"], "verified")


if __name__ == "__main__":
    unittest.main()
