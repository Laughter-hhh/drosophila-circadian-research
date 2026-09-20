import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.plot_circadian_timeseries import plot


class CircadianPlotTests(unittest.TestCase):
    def setUp(self):
        self.input_path = ROOT / "validation" / "synthetic-ephys-trace-derived.csv"

    def test_svg_export_is_deterministic_and_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            svg_a = directory / "figure-a.svg"
            report_a = directory / "figure-a.json"
            result_a = plot(self.input_path, svg_a, report_a, time_system="ZT")
            svg_b = directory / "figure-b.svg"
            report_b = directory / "figure-b.json"
            result_b = plot(self.input_path, svg_b, report_b, time_system="ZT")
            self.assertEqual(result_a["status"], "verified_visualization_export")
            self.assertEqual(result_a["scientific_status"], "not_a_rhythm_test")
            self.assertEqual(result_a["n_rows"], 4)
            self.assertEqual(result_a["n_groups"], 4)
            self.assertIn("raw rows", result_a["inference_warning"])
            self.assertEqual(hashlib.sha256(svg_a.read_bytes()).hexdigest(), hashlib.sha256(svg_b.read_bytes()).hexdigest())
            self.assertEqual(json.loads(report_a.read_text(encoding="utf-8"))["output_file_metadata"]["sha256"], result_a["output_file_metadata"]["sha256"])
            self.assertIn("<circle", svg_a.read_text(encoding="utf-8"))

    def test_missing_time_system_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                plot(self.input_path, Path(directory) / "figure.svg", Path(directory) / "report.json", time_system="")

    def test_mixed_metric_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mixed.csv"
            with self.input_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[1]["metric_name"] = "calcium_signal"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                plot(path, Path(directory) / "figure.svg", Path(directory) / "report.json", time_system="ZT")

    def test_missing_group_column_is_rejected_instead_of_silent_pooling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ungrouped.csv"
            path.write_text("time_hours,value,metric_name,value_unit\n0,1,resting_membrane_potential,mV\n6,2,resting_membrane_potential,mV\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "group column"):
                plot(path, Path(directory) / "figure.svg", Path(directory) / "report.json", time_system="ZT")

    def test_nonfinite_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.csv"
            text = self.input_path.read_text(encoding="utf-8").replace(",12.15,", ",nan,")
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                plot(path, Path(directory) / "figure.svg", Path(directory) / "report.json", time_system="ZT")


if __name__ == "__main__":
    unittest.main()
