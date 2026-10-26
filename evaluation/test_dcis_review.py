"""Offline tests; synthetic arithmetic fixtures are not reference labels."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dcis_review as review
import run_evaluation as evaluation


class DcisReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / "evaluation/dcis"
        (self.pack / "source").mkdir(parents=True)
        (self.root / "data/rules/drafts").mkdir(parents=True)
        (self.root / "synthetic patient").mkdir()
        self.patients = [{"patient_id": p, "consent": None} for p in review.PATIENT_IDS]
        self.rules = [{"rule_id": f"{review.TRIAL}_{i:02}", "rule_text": f"Fixture rule {i}",
                       "source_text": "Fixture criterion", "type": "inclusion"} for i in range(1, 21)]
        (self.root / "synthetic patient/synthetic_patients_simple.json").write_text(json.dumps(self.patients))
        (self.root / f"data/rules/drafts/{review.TRIAL}.json").write_text(json.dumps({"rules": self.rules}))
        self.criteria = "Inclusion Criteria:\n\n1. Fixture criterion\n\nExclusion Criteria:\n\n1. Other fixture"
        (self.pack / "source/NCT04916808.registry.json").write_text(json.dumps({"protocolSection": {
            "identificationModule": {"nctId": review.TRIAL},
            "eligibilityModule": {"eligibilityCriteria": self.criteria},
            "statusModule": {"lastUpdatePostDateStruct": {"date": "2026-01-01"}},
        }}))
        self.patches = patch.multiple(review, ROOT=self.root, PACK=self.pack)
        self.patches.start()
        self.addCleanup(self.patches.stop)
        with redirect_stdout(io.StringIO()):
            review.prepare()

    def test_expected_labels_start_blank_and_no_network(self):
        rows = evaluation.read_csv(self.pack / "labels/agent2_reference.csv")
        self.assertEqual(len(rows), 60)
        self.assertTrue(all(not r["expected_result"] for r in rows))
        table = evaluation.read_csv(self.pack / "coordinator_only/agent2_review_table.csv")
        self.assertTrue(all(r["actual_prediction"] == "Not collected" for r in table))

    def test_prepare_preserves_human_edits(self):
        path = self.pack / "labels/agent2_reference.csv"
        rows = evaluation.read_csv(path)
        rows[0]["reference_evidence"] = "Human work must survive"
        evaluation.write_csv(path, rows, rows[0].keys())
        with redirect_stdout(io.StringIO()):
            review.prepare()
        self.assertEqual(evaluation.read_csv(path)[0]["reference_evidence"], "Human work must survive")

    def test_changed_patient_snapshot_blocks_review(self):
        (self.pack / "patient_profiles.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "snapshots changed"):
            review.prepare()

    def test_no_predictions_cannot_be_evaluated(self):
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "No saved DCIS predictions"):
            review.evaluate()

    def add_predictions(self):
        path = self.pack / "predictions"
        path.mkdir()
        records = [{"patient_id": p["patient_id"], "trial_id": review.TRIAL,
                    "patient_sha256": evaluation.object_hash(p),
                    "agent1": {"status": "success", "rules": self.rules},
                    "agent2": {"status": "success", "results": [
                        {"rule_id": r["rule_id"], "result": "Unknown", "reason": "Fixture missing consent"}
                        for r in self.rules]}} for p in self.patients]
        (path / "pipeline_predictions.json").write_text(json.dumps({"records": records}))

    def test_collection_never_overwrites_frozen_predictions(self):
        self.add_predictions()
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "already frozen"):
            review.collect()

    def test_saved_model_unknowns_do_not_approve_human_labels(self):
        self.add_predictions()
        review.refresh_tables()
        rows = evaluation.read_csv(self.pack / "coordinator_only/agent2_review_table.csv")
        self.assertTrue(all(r["actual_prediction"] == "Unknown" and not r["expected_result"] for r in rows))
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "human adjudication"):
            review.evaluate()

    def test_fixed_sample_has_twelve_unique_cases(self):
        self.assertEqual(len(set(review.SAMPLE)), 12)
        self.assertEqual({p: sum(x == p for x, _ in review.SAMPLE) for p in review.PATIENT_IDS},
                         {p: 4 for p in review.PATIENT_IDS})

    def test_explanation_ratings_need_two_people_and_matching_artifact(self):
        self.add_predictions()
        reference_path = self.pack / "labels/agent2_reference.csv"
        refs = evaluation.read_csv(reference_path)
        for r in refs:
            r.update(review_status="verified", reviewed_by="Fixture human", independent="yes", reference_evidence="Fixture")
        evaluation.write_csv(reference_path, refs, refs[0].keys())
        path = self.pack / "labels/explanation_review.csv"
        rows = evaluation.read_csv(path)
        prediction_hash = evaluation.digest(self.pack / "predictions/pipeline_predictions.json")
        for r in rows:
            r.update({s: "2" for s in review.SCORES})
            r.update(reviewer="Same person", prediction_sha256=prediction_hash)
        evaluation.write_csv(path, rows, rows[0].keys())
        self.assertEqual(review.explanation_metrics()["paired_cases"], 0)
        for r in rows:
            r["reviewer"] = r["review_slot"]
        evaluation.write_csv(path, rows, rows[0].keys())
        result = review.explanation_metrics()
        self.assertEqual(result["paired_cases"], 12)
        self.assertTrue(all(d["mean"] == 2 and d["exact_interreviewer_agreement"] == 1 for d in result["dimensions"].values()))


if __name__ == "__main__":
    unittest.main()
