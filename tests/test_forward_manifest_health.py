import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import replay_file
from scripts.validate_public_dataset_manifest import validate_file


FORWARD_MANIFESTS = (
    ("GSE22308-blind-forward-context-stratified-manifest.json", 4, 6),
    ("GSE22308-blind-forward-sex-aware-manifest.json", 4, 6),
    ("GSE77451-candidate-transcript-key-manifest.json", 1, 1),
)


class ForwardManifestHealthTests(unittest.TestCase):
    def test_checked_in_forward_manifests_are_verified_and_replayable(self):
        for name, expected_runs, expected_outputs in FORWARD_MANIFESTS:
            with self.subTest(manifest=name):
                manifest = ROOT / "validation" / "public-data" / name
                validation = validate_file(manifest, ROOT)
                self.assertEqual(validation["status"], "verified_public_dataset_manifest", validation.get("issues"))
                self.assertEqual(validation["manifest_stage"], "verified")
                self.assertEqual(validation["n_runs"], expected_runs)
                replay = replay_file(manifest, ROOT, timeout_seconds=180)
                self.assertEqual(replay["status"], "verified_public_dataset_replay", replay.get("issues"))
                self.assertEqual(replay["manifest_validation"]["manifest_stage"], "verified")
                self.assertEqual(replay["n_runs"], expected_runs)
                self.assertEqual(replay["n_output_checks"], expected_outputs)


if __name__ == "__main__":
    unittest.main()
