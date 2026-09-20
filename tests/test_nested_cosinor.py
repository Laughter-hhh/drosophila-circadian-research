import csv
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_nested_cosinor import analyze_file


class NestedCosinorTests(unittest.TestCase):
    def _write(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        fields = ["biological_replicate_id", "subunit_id", "time_hours", "value", "experimental_unit", "gene_symbol", "cell_type", "background"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _rows(self, amplitude=0.0, n_flies=8, include_unit=True):
        rows = []
        for fly_index in range(n_flies):
            for time in [0.0, 6.0, 12.0, 18.0]:
                signal = 5.0 + amplitude * math.cos(2.0 * math.pi * time / 24.0)
                for subunit_index in range(2):
                    rows.append({
                        "biological_replicate_id": f"fly{fly_index}", "subunit_id": f"fly{fly_index}_cell{subunit_index}",
                        "time_hours": time, "value": signal + (subunit_index - 0.5) * 0.1 + (fly_index % 3 - 1) * 0.03,
                        "experimental_unit": "fly" if include_unit else "", "gene_symbol": "na", "cell_type": "s-LNv", "background": "w1118",
                    })
        return rows

    def test_time_system_is_required(self):
        path = self._write(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_time_system_unspecified")

    def test_nested_units_are_aggregated_and_strong_rhythm_detected(self):
        path = self._write(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=200, n_bootstrap=200, seed=7, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "exploratory_nested_cosinor")
        self.assertEqual(group["n_raw_observations"], 64)
        self.assertEqual(group["n_aggregated_biological_unit_time_means"], 32)
        self.assertEqual(group["n_biological_replicates"], 8)
        self.assertEqual(group["max_subunits_per_biological_unit_time"], 2)
        self.assertEqual(group["permutation_mode"], "within_biological_unit_time_shuffle")
        self.assertLess(group["p_amplitude_permutation"], 0.05)

    def test_flat_nested_signal_does_not_become_rhythmic(self):
        path = self._write(self._rows(amplitude=0.0))
        try:
            result = analyze_file(path, n_permutations=200, n_bootstrap=200, seed=7, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "exploratory_nested_cosinor")
        self.assertGreater(group["p_amplitude_permutation"], 0.1)

    def test_unspecified_unit_is_blocked(self):
        path = self._write(self._rows(amplitude=4.0, include_unit=False))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_experimental_unit_unspecified")

    def test_too_few_biological_replicates_are_not_rescued_by_cells(self):
        path = self._write(self._rows(amplitude=4.0, n_flies=3))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "insufficient_or_invalid_nested_time_series")
        self.assertEqual(group["n_biological_replicates"], 3)
        self.assertEqual(group["n_raw_observations"], 24)


if __name__ == "__main__":
    unittest.main()
