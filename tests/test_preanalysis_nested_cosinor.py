import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from scripts.analyze_preanalysis_nested_cosinor import analyze_bundle


class PreanalysisNestedCosinorTests(unittest.TestCase):
    def setUp(self):
        self.metadata = ROOT / "validation" / "synthetic-ephys-nested-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-ephys-nested-raw-qc.csv"
        self.measurements = ROOT / "validation" / "synthetic-ephys-nested-derived.csv"

    def test_cluster_permutation_and_bootstrap_use_biological_units(self):
        result = analyze_bundle(
            self.metadata,
            self.raw_qc,
            self.measurements,
            time_system="ZT",
            metric_name="resting_membrane_potential",
            n_permutations=50,
            n_bootstrap=50,
            seed=7,
        )
        self.assertEqual(result["status"], "verified_exploratory_bundle_nested_cosinor")
        self.assertEqual(result["time_system"], "ZT")
        self.assertEqual(result["n_selected_measurements"], 32)
        group = result["groups"][0]
        self.assertEqual(group["status"], "exploratory_nested_cosinor")
        self.assertEqual(group["experimental_unit"], "fly")
        self.assertEqual(group["n_biological_replicates"], 4)
        self.assertEqual(group["n_aggregated_biological_unit_time_means"], 16)
        self.assertEqual(group["max_subunits_per_biological_unit_time"], 2)
        self.assertEqual(group["permutation_mode"], "within_biological_unit_time_shuffle")
        self.assertEqual(group["n_bootstrap_success"], 50)
        self.assertAlmostEqual(group["observed_amplitude"], 2.0, places=8)

    def test_formal_stage_is_blocked_even_when_bundle_passes(self):
        result = analyze_bundle(self.metadata, self.raw_qc, self.measurements, stage="formal", metric_name="resting_membrane_potential")
        self.assertEqual(result["status"], "blocked_formal_nested_cosinor_requires_mixed_model")
        self.assertEqual(result["bundle_gate"]["status"], "verified_preanalysis_bundle")

    def test_orphan_measurement_is_blocked_by_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orphan.csv"
            path.write_text(self.measurements.read_text(encoding="utf-8") + "orphan,meta01,fly01,6,10,resting_membrane_potential,mV,cellC\n", encoding="utf-8")
            result = analyze_bundle(self.metadata, self.raw_qc, path, time_system="ZT", metric_name="resting_membrane_potential", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertEqual(result["bundle_gate"]["status"], "blocked_preanalysis_bundle")

    def test_multiple_metrics_require_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two_metrics.csv"
            extra = "rec01,meta01,fly01,0,12.0,calcium_signal,AU,roi1\n"
            path.write_text(self.measurements.read_text(encoding="utf-8") + extra, encoding="utf-8")
            result = analyze_bundle(self.metadata, self.raw_qc, path, time_system="ZT", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertEqual(result["issues"][0]["type"], "multiple_metrics_unspecified")


if __name__ == "__main__":
    unittest.main()
