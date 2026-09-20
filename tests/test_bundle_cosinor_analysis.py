import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from scripts.analyze_preanalysis_cosinor import analyze_bundle


class BundleCosinorAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.metadata = ROOT / "validation" / "synthetic-ephys-bundle-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-ephys-raw-qc.csv"
        self.measurements = ROOT / "validation" / "synthetic-ephys-cosinor-derived.csv"

    def test_averages_technical_repeats_and_fits_verified_bundle(self):
        result = analyze_bundle(
            self.metadata,
            self.raw_qc,
            self.measurements,
            time_system="ZT",
            group_by=("cell_type", "genotype"),
        )
        self.assertEqual(result["status"], "verified_exploratory_bundle_cosinor")
        self.assertEqual(result["n_fit_groups"], 1)
        fit = result["groups"][0]
        self.assertEqual(fit["status"], "exploratory_descriptive_fit")
        self.assertEqual(fit["n_biological_replicates"], 2)
        self.assertEqual(fit["n_aggregated_observations"], 8)
        self.assertEqual(fit["n_technical_measurements"], 9)
        self.assertAlmostEqual(fit["mesor"], 10.5, places=8)
        self.assertAlmostEqual(fit["amplitude"], 1.5811388300841895, places=8)
        self.assertEqual(fit["design"], "longitudinal")
        self.assertEqual(result["input_gate"], "verified_preanalysis_bundle")
        self.assertEqual(result["scientific_status"], "exploratory_not_verified")

    def test_formal_stage_is_explicitly_blocked_after_bundle_pass(self):
        result = analyze_bundle(self.metadata, self.raw_qc, self.measurements, stage="formal")
        self.assertEqual(result["status"], "blocked_formal_cosinor_requires_mixed_model")
        self.assertEqual(result["bundle_gate"]["status"], "verified_preanalysis_bundle")

    def test_orphan_measurement_is_blocked_before_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orphan.csv"
            path.write_text(self.measurements.read_text(encoding="utf-8") + "orphan,meta01,fly01,6,10\n", encoding="utf-8")
            result = analyze_bundle(self.metadata, self.raw_qc, path, time_system="ZT")
        self.assertEqual(result["status"], "blocked_preanalysis_cosinor")
        self.assertEqual(result["bundle_gate"]["status"], "blocked_preanalysis_bundle")

    def test_insufficient_group_is_reported_without_fake_fit(self):
        result = analyze_bundle(self.metadata, self.raw_qc, self.measurements, time_system="ZT", min_unique_times=5)
        self.assertEqual(result["status"], "verified_exploratory_bundle_cosinor")
        self.assertEqual(result["n_fit_groups"], 0)
        self.assertEqual(result["n_insufficient_groups"], 1)
        self.assertEqual(result["groups"][0]["status"], "insufficient_time_coverage")


if __name__ == "__main__":
    unittest.main()
