import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_candidates import score_row
from scripts.validate_candidate_evidence import validate as validate_candidate_table
from scripts.validate_pharmacology_bundle import validate as validate_pharmacology_bundle
from scripts.validate_pharmacology_source_log import validate as validate_pharmacology_source_log


PUBLIC = ROOT / "validation" / "public-data"


def read_csv_rows(name):
    with (PUBLIC / name).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise AssertionError(f"Malformed CSV row in {name}")
    return rows


class PrimaryChannelEvidenceAuditTests(unittest.TestCase):
    def test_ruben_2012_is_mapped_to_irk1_and_behavior_is_not_ephys_directness(self):
        sources = read_csv_rows("circadian_channel_primary_sources.csv")
        pubmed_2012 = [row for row in sources if row["doi_or_pmid"] == "10.1177/0748730412455918"]
        self.assertEqual(len(pubmed_2012), 1)
        self.assertEqual(pubmed_2012[0]["candidate"], "Irk1")
        self.assertIn("not native electrophysiology", pubmed_2012[0]["evidence_level"])

        log_rows = [row for row in read_csv_rows("candidate-evidence-search-log.csv") if row["source_id"] == "PMID:23010658"]
        self.assertEqual({row["candidate"] for row in log_rows}, {"Irk1"})
        behavior = next(row for row in log_rows if row["readout_match"] == "behavior_only")
        self.assertEqual(behavior["evidence_label"], "indirect")
        self.assertIn("no electrophysiological current", behavior["result_summary"])

    def test_na_direct_ephys_is_scoped_to_dn1p(self):
        sources = read_csv_rows("circadian_channel_primary_sources.csv")
        na_source = next(row for row in sources if row["candidate"] == "na")
        self.assertEqual(na_source["neuron_or_system"], "DN1p only")
        self.assertIn("NMDG-sensitive Na+ leak current", na_source["readout"])
        self.assertIn("does not establish the same current", na_source["claim_scope"])

        candidates = read_csv_rows("candidate-evidence-real.csv")
        na = next(row for row in candidates if row["candidate"] == "na")
        self.assertEqual(na["evidence_label"], "direct")
        self.assertEqual(score_row(na, target_cells=["DN1p"])["directness_gate"], "pass")
        self.assertIn("DN1p", na["keep_drop_reason"])

    def test_irk1_native_and_cultured_cell_readouts_remain_separated(self):
        sources = read_csv_rows("circadian_channel_primary_sources.csv")
        schellinger = next(row for row in sources if row["doi_or_pmid"] == "10.1016/j.cub.2022.03.017")
        self.assertIn("s-LNv in vivo", schellinger["neuron_or_system"])
        self.assertIn("S2-R+ cultured cells", schellinger["neuron_or_system"])
        self.assertIn("not native s-LNv", schellinger["claim_scope"])

    def test_smith_pharmacology_rows_are_well_formed_and_remain_pilot_only(self):
        expected = {
            "Shaker": ("alpha-Dendrotoxin (DTX)", "100"),
            "Shab": ("Guangxitoxin-1E (GxTX)", "20"),
            "Shaw": ("blood-dispersing substance (BDS)", "300"),
            "Shal": ("Phrixotoxin-1 (PaTX)", "100"),
        }
        plans = read_csv_rows("primary-pharmacology-methods.csv")
        self.assertEqual(len(plans), 4)
        for row in plans:
            blocker, concentration = expected[row["candidate"]]
            self.assertEqual(row["blocker"], blocker)
            self.assertEqual(row["concentration"], concentration)
            self.assertEqual(row["stage"], "conditional_pilot")
            self.assertEqual(row["selectivity_status"], "native_verified")
            self.assertEqual(row["dose_response_status"], "not_assessed")
            self.assertEqual(row["washout_status"], "needs_confirmation")
            self.assertEqual(row["scope"], "primary-paper starting condition")
            self.assertIn("local-potency risk", row["off_target_risk"])

        source_result = validate_pharmacology_source_log(PUBLIC / "primary-pharmacology-source-log.csv")
        self.assertEqual(source_result["status"], "verified_pharmacology_source_log")
        bundle = validate_pharmacology_bundle(
            PUBLIC / "primary-pharmacology-methods.csv",
            PUBLIC / "primary-pharmacology-source-log.csv",
        )
        self.assertEqual(bundle["status"], "verified_pharmacology_bundle")
        self.assertEqual(bundle["formal_status"], "conditional_pilot_only")

    def test_real_candidate_table_and_search_log_jointly_validate(self):
        result = validate_candidate_table(
            PUBLIC / "candidate-evidence-real.csv",
            PUBLIC / "candidate-evidence-search-log.csv",
        )
        self.assertEqual(result["status"], "verified_candidate_evidence_table")
        self.assertEqual(result["evidence_search_log"]["status"], "verified_evidence_search_log")


if __name__ == "__main__":
    unittest.main()
