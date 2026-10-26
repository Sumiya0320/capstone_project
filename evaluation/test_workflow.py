"""Exercise reference gates and saved-output handling without any API calls."""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_evaluation as runner


class WorkflowTests(unittest.TestCase):
    def test_duplicate_predictions_or_references_rejected(self):
        with self.assertRaises(ValueError):
            runner.unique([{"id": "A"}, {"id": "A"}], ("id",))

    def test_patient_hash_is_stable_across_key_order(self):
        self.assertEqual(runner.object_hash({"a": 1, "b": 2}), runner.object_hash({"b": 2, "a": 1}))

    def exercise(self, verify=False, prediction=None, stale=False, review_extraction=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            here = root / "evaluation"
            here.mkdir()
            (root / "data/rules/raw").mkdir(parents=True)
            (root / "synthetic patient").mkdir()
            (root / "synthetic patient/synthetic_patients_simple.json").write_text('[{"patient_id":"P"}]')
            rules = [{"rule_id": "T_1", "rule_text": "Consent ability documented"}]
            (root / "data/rules/raw/T.json").write_text(json.dumps({"rules": rules}))
            runner.write_csv(here / "ground_truth_rule_level_detail.csv", [{
                "patient_id": "P", "trial_id": "T", "rule_id": "T_1", "expected_result": "Unknown",
            }], ("patient_id", "trial_id", "rule_id", "expected_result"))
            runner.write_csv(here / "ground_truth_test_set.csv", [{
                "patient_id": "P", "trial_id": "T", "expected_overall": "Needs Review",
            }], ("patient_id", "trial_id", "expected_overall"))
            args = argparse.Namespace(collect=False, run_dcis=False, predictions=None)
            completed = subprocess.CompletedProcess([], 0, "1 passed, 0 failed out of 1 tests", "")
            with patch.object(runner, "ROOT", root), patch.object(runner, "HERE", here), patch.object(
                runner.subprocess, "run", return_value=completed
            ), redirect_stdout(io.StringIO()):
                runner.run(args)
                if review_extraction:
                    evidence = {"review_status": "verified", "reviewed_by": "Human",
                                "independent": "yes", "reference_evidence": "Fixture source"}
                    source = root / "criteria.txt"
                    source.write_text("Consent ability documented. Age greater than 25.")
                    path = here / "labels/agent1_trials.csv"
                    rows = runner.read_csv(path)
                    rows[0].update(**evidence, reference_complete="yes", source_file="criteria.txt",
                                   source_sha256=runner.digest(source))
                    runner.write_csv(path, rows, rows[0].keys())
                    path = here / "labels/agent1_matches.csv"
                    rows = runner.read_csv(path)
                    rows[0].update(**evidence, reference_id="R1")
                    runner.write_csv(path, rows, rows[0].keys())
                    rows = [{**evidence, "trial_id": "T", "reference_id": rid,
                             "reference_rule": quote, "source_quote": quote}
                            for rid, quote in [("R1", "Consent ability documented"), ("R2", "Age greater than 25")]]
                    runner.write_csv(here / "labels/agent1_reference.csv", rows, rows[0].keys())
                if verify:
                    path = here / "labels/agent2_reference.csv"
                    rows = runner.read_csv(path)
                    rows[0].update(review_status="verified", reviewed_by="Independent reviewer",
                                   independent="yes", reference_evidence="Fixture: no consent field",
                                   unknown_cause="missing_information")
                    runner.write_csv(path, rows, rows[0].keys())
                if prediction is not None:
                    (here / "results/pipeline_predictions.json").write_text(json.dumps({"records": [{
                        "patient_id": "P", "trial_id": "T",
                        "patient_sha256": "stale" if stale else runner.object_hash({"patient_id": "P"}),
                        "agent1": {"status": "success", "rules": rules},
                        "agent2": {"status": "success", "summary": {"overall": "Needs Review"},
                                   "results": [{"rule_id": "T_1", "result": "Unknown", "reason": prediction}]},
                    }]}))
                runner.run(args)
            return json.loads((here / "results/evaluation_summary.json").read_text())

    def test_unreviewed_labels_never_count(self):
        result = self.exercise()
        self.assertEqual(result["agent2"]["total"], 0)
        self.assertIsNone(result["agent2"]["accuracy"])
        self.assertEqual(result["agent1"]["status"], "Not Yet Evaluated")

    def test_fully_adjudicated_extraction_includes_omitted_reference(self):
        result = self.exercise(review_extraction=True)
        self.assertEqual(result["agent1"]["correctly_extracted"], 1)
        self.assertEqual(result["agent1"]["missing"], 1)
        self.assertEqual(result["agent1"]["precision"], 1)
        self.assertEqual(result["agent1"]["recall"], 0.5)
        self.assertEqual(result["agent1"]["f1"], 2 / 3)

    def test_technical_unknown_is_error_in_full_denominator(self):
        result = self.exercise(verify=True, prediction="[API ERROR -- not a real data gap]")
        self.assertEqual(result["agent2"]["total"], 1)
        self.assertEqual(result["agent2"]["incorrect"], 1)
        self.assertEqual(result["missing_information"]["unknown_recall"], 0)

    def test_independent_missing_information_unknown_is_correct(self):
        result = self.exercise(verify=True, prediction="Consent ability is not documented")
        self.assertEqual(result["agent2"]["accuracy"], 1)
        self.assertEqual(result["missing_information"]["unknown_recall"], 1)
        self.assertEqual(result["missing_information"]["unknown_precision_for_missing_information"], 1)

    def test_stale_predictions_are_errors(self):
        result = self.exercise(verify=True, prediction="Consent ability is not documented", stale=True)
        self.assertEqual(result["agent2"]["correct"], 0)
        self.assertEqual(result["missing_information"]["technical_or_missing_predictions"], 1)


if __name__ == "__main__":
    unittest.main()
