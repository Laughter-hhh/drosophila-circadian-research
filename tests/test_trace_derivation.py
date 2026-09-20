import csv
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_trace_measurements import derive


class TraceDerivationTests(unittest.TestCase):
    def setUp(self):
        self.traces = ROOT / "validation" / "synthetic-ephys-traces.csv"
        self.metadata = ROOT / "validation" / "synthetic-ephys-trace-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-ephys-nested-raw-qc.csv"

    def test_ephys_trace_is_qc_gated_and_time_anchored_to_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(self.traces, self.metadata, self.raw_qc, output, report, check_files=True, metric_name="resting_membrane_potential", value_unit="mV")
            self.assertEqual(result["status"], "verified_trace_derivation")
            self.assertEqual(result["n_trace_rows"], 16)
            self.assertEqual(result["n_output_rows"], 4)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["time_hours"] for row in rows], ["0", "6", "12", "18"])
            self.assertEqual([row["value"] for row in rows], ["12.15", "10.15", "8.15", "10.15"])
            self.assertEqual({row["metric_name"] for row in rows}, {"resting_membrane_potential"})
            self.assertEqual({row["value_unit"] for row in rows}, {"mV"})
            self.assertEqual({row["time_basis"] for row in rows}, {"metadata_ZT_or_CT"})
            self.assertTrue(result["output_file_metadata"]["sha256"])

    def test_long_trace_can_preserve_binned_timepoints_with_explicit_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = Path(directory) / "long.csv"
            rows = ["record_id,time_seconds,value"]
            for record_index, record_id in enumerate(("rec01", "rec02", "rec03", "rec04")):
                for hour in range(4):
                    for replicate in range(4):
                        rows.append(f"{record_id},{hour * 3600 + replicate * 300},{10 + record_index + hour + replicate / 10:g}")
            traces.write_text("\n".join(rows) + "\n", encoding="utf-8")
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(traces, self.metadata, self.raw_qc, output, report, check_files=True, metric_name="resting_membrane_potential", value_unit="mV", time_mode="metadata_plus_elapsed", time_bin_seconds=3600)
            self.assertEqual(result["status"], "verified_trace_derivation")
            self.assertEqual(result["n_output_rows"], 16)
            with output.open(newline="", encoding="utf-8") as handle:
                output_rows = list(csv.DictReader(handle))
            self.assertEqual([row["time_hours"] for row in output_rows[:4]], ["0", "1", "2", "3"])
            self.assertEqual({row["time_basis"] for row in output_rows}, {"metadata_ZT_or_CT_plus_elapsed"})
            self.assertTrue(any(warning["type"] == "elapsed_time_anchored_to_metadata" for warning in result["warnings"]))

    def test_pass_record_without_trace_blocks_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = Path(directory) / "missing.csv"
            lines = self.traces.read_text(encoding="utf-8").splitlines()
            traces.write_text("\n".join(lines[:-4]) + "\n", encoding="utf-8")
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(traces, self.metadata, self.raw_qc, output, report)
            self.assertEqual(result["status"], "blocked_trace_derivation")
            self.assertEqual(result["n_output_rows"], 0)
            self.assertFalse(output.exists())
            self.assertTrue(any(issue["type"] == "pass_record_without_trace" for issue in result["issues"]))

    def test_nonfinite_trace_value_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = Path(directory) / "nan.csv"
            text = self.traces.read_text(encoding="utf-8").replace("rec01,1,12.2", "rec01,1,nan")
            traces.write_text(text, encoding="utf-8")
            output = Path(directory) / "derived.csv"
            report = Path(directory) / "report.json"
            result = derive(traces, self.metadata, self.raw_qc, output, report)
            self.assertEqual(result["status"], "blocked_trace_derivation")
            self.assertTrue(any(issue["type"] == "invalid_trace_value" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
