import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_circadian_timeseries import analyze_rows


class CircadianAnalysisTests(unittest.TestCase):
    def _rows(self):
        rows = []
        for subject in ("f1", "f2", "f3"):
            for time in (0, 4, 8, 12, 16, 20):
                theta = 2 * math.pi * time / 24
                value = 10 + 4 * math.cos(theta) + 3 * math.sin(theta)
                rows.append({"subject_id": subject, "time_hours": str(time), "value": str(value)})
        return rows

    def test_recovers_known_fixed_period_signal(self):
        rows = self._rows()
        result = analyze_rows(rows, period_hours=24, time_system="ZT")
        self.assertAlmostEqual(result["mesor"], 10.0, places=8)
        self.assertAlmostEqual(result["amplitude"], 5.0, places=8)
        self.assertAlmostEqual(result["phase_peak_hours"], 24 * math.atan2(3, 4) / (2 * math.pi), places=8)
        self.assertAlmostEqual(result["r_squared"], 1.0, places=8)
        self.assertEqual(result["n_subjects"], 3)
        self.assertEqual(result["time_system"], "ZT")
        self.assertEqual(result["status"], "exploratory_fixed_period_cosinor")

    def test_time_system_is_required_and_normalized(self):
        with self.assertRaisesRegex(ValueError, "time_system must be ZT or CT"):
            analyze_rows(self._rows())
        self.assertEqual(analyze_rows(self._rows(), time_system="ct")["time_system"], "CT")

    def test_nonfinite_time_or_value_is_rejected(self):
        rows = [{"subject_id": "f1", "time_hours": str(time), "value": "1"} for time in (0, 6, 12, 18)]
        rows[0]["time_hours"] = "nan"
        with self.assertRaisesRegex(ValueError, "finite"):
            analyze_rows(rows, time_system="ZT")
        rows[0]["time_hours"] = "0"
        rows[0]["value"] = "inf"
        with self.assertRaisesRegex(ValueError, "finite"):
            analyze_rows(rows, time_system="ZT")


if __name__ == "__main__":
    unittest.main()
