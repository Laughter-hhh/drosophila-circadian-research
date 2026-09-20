import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_circadian_timeseries import analyze_rows


class CosinorPhaseBoundaryTests(unittest.TestCase):
    def test_zero_sine_phase_is_canonical_zero_not_period(self):
        rows = [
            {"subject_id": "fly01", "time_hours": "0", "value": "12"},
            {"subject_id": "fly01", "time_hours": "6", "value": "10"},
            {"subject_id": "fly01", "time_hours": "12", "value": "8"},
            {"subject_id": "fly01", "time_hours": "18", "value": "10"},
        ]
        result = analyze_rows(rows, time_system="ZT")
        self.assertEqual(result["phase_peak_hours"], 0.0)
        self.assertGreaterEqual(result["phase_peak_hours"], 0.0)
        self.assertLess(result["phase_peak_hours"], result["period_hours"])


if __name__ == "__main__":
    unittest.main()
