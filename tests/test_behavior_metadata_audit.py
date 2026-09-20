import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_public_behavior_metadata import audit


CSV = ROOT / "validation" / "public-data" / "zenodo-18214640-20lux-main-dataset.csv"
EXPECTED_SHA256 = "1879cb556e1f84a225520b5a4d4689244b7109bfe850261d24dd3137c7fb1008"


class BehaviorMetadataAuditTests(unittest.TestCase):
    def test_real_zenodo_metadata_is_verified_but_not_analysis_ready(self):
        result = audit(
            CSV,
            "https://zenodo.org/records/18214640",
            EXPECTED_SHA256,
            "validation/public-data/zenodo-18214640-20lux-main-dataset.csv",
        )
        self.assertEqual(result["status"], "verified_public_behavior_metadata_audit")
        self.assertEqual(result["analysis_readiness"], "blocked_metadata_insufficient_for_behavior_analysis")
        self.assertEqual(result["n_rows"], 190)
        self.assertEqual(result["condition_counts"], {"A": 50, "B": 50, "C": 50, "D": 40})
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["input_file_metadata"]["path"], "validation/public-data/zenodo-18214640-20lux-main-dataset.csv")
        self.assertIn("genotype/strain", result["missing_research_metadata"])

    def test_hash_mismatch_is_reported_without_biological_inference(self):
        result = audit(
            CSV,
            "https://zenodo.org/records/18214640",
            "0" * 64,
            "validation/public-data/zenodo-18214640-20lux-main-dataset.csv",
        )
        self.assertEqual(result["status"], "blocked_public_behavior_metadata_audit")
        self.assertTrue(any(issue["type"] == "input_sha256_mismatch" for issue in result["issues"]))
        self.assertEqual(result["analysis_readiness"], "blocked_metadata_insufficient_for_behavior_analysis")

    def test_checked_report_is_json_serializable(self):
        result = audit(
            CSV,
            "https://zenodo.org/records/18214640",
            EXPECTED_SHA256,
            "validation/public-data/zenodo-18214640-20lux-main-dataset.csv",
        )
        json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()


