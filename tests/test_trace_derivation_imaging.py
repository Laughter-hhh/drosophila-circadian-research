import csv
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_trace_measurements import derive


class ImagingTraceDerivationTests(unittest.TestCase):
    def setUp(self):
        self.traces = ROOT / "validation" / "synthetic-imaging-traces.csv"
        self.metadata = ROOT / "validation" / "synthetic-imaging-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-imaging-raw-qc.csv"

    def test_imaging_trace_emits_one_measurement_per_roi_with_explicit_provisional_override(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(self.traces, self.metadata, self.raw_qc, output, report, assay="imaging", check_files=False, metric_name="mean_fluorescence", value_unit="AU")
            self.assertEqual(result["status"], "verified_trace_derivation")
            self.assertTrue(any(warning["type"] == "raw_hash_check_disabled" for warning in result["warnings"]))
            self.assertEqual(result["n_output_rows"], 2)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["subunit_id"] for row in rows], ["roi01", "roi02"])
            self.assertEqual([row["value"] for row in rows], ["107.5", "87.5"])
            self.assertEqual({row["time_hours"] for row in rows}, {"4"})
            self.assertEqual({row["time_basis"] for row in rows}, {"metadata_ZT_or_CT"})

    def test_imaging_roi_count_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "bad_raw.csv"
            raw.write_text(self.raw_qc.read_text(encoding="utf-8").replace(",2,0.1,0.1,8.5", ",3,0.1,0.1,8.5"), encoding="utf-8")
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(self.traces, self.metadata, raw, output, report, assay="imaging", check_files=False, metric_name="mean_fluorescence", value_unit="AU")
        self.assertEqual(result["status"], "blocked_trace_derivation")
        self.assertTrue(any(issue["type"] == "roi_count_mismatch" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
