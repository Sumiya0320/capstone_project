"""Deterministic metric checks with invented arithmetic fixtures, not study results."""

import unittest

from metrics import approved, classification, extraction, technical_failure


class MetricsTests(unittest.TestCase):
    def test_classification_and_confusion(self):
        result = classification([("Met", "Met", False), ("Met", "Unknown", False),
                                 ("Unknown", "Unknown", False), ("Not Met", "Met", False)])
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["per_class"]["Unknown"]["precision"], 0.5)
        self.assertEqual(result["per_class"]["Unknown"]["recall"], 1)
        self.assertEqual(result["per_class"]["Unknown"]["f1"], 2 / 3)
        self.assertEqual(result["confusion_matrix"]["Met"]["Unknown"], 1)

    def test_technical_unknown_is_not_correct(self):
        result = classification([("Unknown", "Unknown", True), ("Unknown", None, True)])
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["per_class"]["Unknown"]["recall"], 0)
        self.assertIsNone(result["per_class"]["Unknown"]["precision"])
        self.assertEqual(result["confusion_matrix"]["Unknown"]["Technical/Missing"], 2)

    def test_no_data_is_not_zero_accuracy(self):
        result = classification([])
        self.assertEqual(result["status"], "Not Yet Evaluated")
        self.assertIsNone(result["accuracy"])

    def test_invalid_reference_fails(self):
        with self.assertRaises(ValueError):
            classification([("made up", "Met", False)])

    def test_extraction_duplicates_are_false_positives(self):
        result = extraction(["R1", "R2", "R3"], ["R1", "R1", "R2", ""])
        self.assertEqual(result["correctly_extracted"], 2)
        self.assertEqual(result["missing"], 1)
        self.assertEqual(result["incorrect_or_unsupported"], 2)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 2 / 3)
        self.assertEqual(result["f1"], 4 / 7)

    def test_unknown_reference_match_rejected(self):
        with self.assertRaises(ValueError):
            extraction(["R1"], ["R2"])

    def test_placeholder_approval_rejected(self):
        self.assertFalse(approved({"review_status": "Agreed (pre-deadline placeholder)"}))
        self.assertFalse(approved({"review_status": "verified", "reviewed_by": "A",
                                   "reference_evidence": "source", "independent": "no"}))
        self.assertTrue(approved({"review_status": "verified", "reviewed_by": "A",
                                  "reference_evidence": "source", "independent": "yes"}))

    def test_failure_reasons(self):
        for text in ("[API ERROR -- not a real data gap]", "LLM not configured",
                     "Unrecognized operator", "Could not compare age='unknown' > 25"):
            self.assertTrue(technical_failure(text), text)
        self.assertFalse(technical_failure("Patient record has no value for 'age'"))
        self.assertFalse(technical_failure("Patient failed prior endocrine therapy"))


if __name__ == "__main__":
    unittest.main()
