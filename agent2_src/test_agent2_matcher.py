"""
Unit tests for agent2_matcher.py's deterministic Python checking logic.

Covers the "Unit test checking functions" item from the capstone Trello board:
tests the operators, missing-value handling, inclusion/exclusion polarity,
OR-group (logic_group) collapsing, and the overall summary/verdict logic --
all without making any real network/API calls (the LLM path is only tested
for its safe "not configured" fallback, which needs no API key).

Run with:
    pip install pytest
    pytest test_agent2_matcher.py -v

Or just:
    python3 test_agent2_matcher.py
(the __main__ block below runs everything with plain asserts if pytest
isn't installed, so this file works either way.)
"""

import os
import sys

# Make sure agent2_matcher.py is importable regardless of which directory
# pytest/python is invoked from (it lives next to this test file).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent2_matcher as m


# ---------------------------------------------------------------------------
# get_nested: plain and dotted/nested field lookup
# ---------------------------------------------------------------------------

def test_get_nested_plain_field():
    patient = {"age": 55}
    assert m.get_nested(patient, "age") == 55


def test_get_nested_dotted_field():
    patient = {"biomarkers": {"HER2_status": "Positive"}}
    assert m.get_nested(patient, "biomarkers.HER2_status") == "Positive"


def test_get_nested_missing_field_returns_none():
    patient = {"age": 55}
    assert m.get_nested(patient, "ecog") is None


def test_get_nested_missing_nested_field_returns_none():
    patient = {"biomarkers": {"ER_status": "Positive"}}
    assert m.get_nested(patient, "biomarkers.HER2_status") is None


def test_get_nested_none_field_name_returns_none():
    patient = {"age": 55}
    assert m.get_nested(patient, None) is None


# ---------------------------------------------------------------------------
# PY_OPERATORS: every operator, including case-insensitive string handling
# ---------------------------------------------------------------------------

def test_operator_gte_lte_gt_lt():
    assert m.PY_OPERATORS[">="](18, 18) is True
    assert m.PY_OPERATORS[">="](17, 18) is False
    assert m.PY_OPERATORS["<="](18, 18) is True
    assert m.PY_OPERATORS["<="](19, 18) is False
    assert m.PY_OPERATORS[">"](19, 18) is True
    assert m.PY_OPERATORS[">"](18, 18) is False
    assert m.PY_OPERATORS["<"](17, 18) is True
    assert m.PY_OPERATORS["<"](18, 18) is False


def test_operator_eq_case_insensitive_strings():
    assert m.PY_OPERATORS["=="]("Positive", "positive") is True
    assert m.PY_OPERATORS["=="](" Positive ", "positive") is True
    assert m.PY_OPERATORS["=="]("Positive", "Negative") is False


def test_operator_eq_numbers():
    assert m.PY_OPERATORS["=="](2, 2) is True
    assert m.PY_OPERATORS["=="](2, 3) is False


def test_operator_neq():
    assert m.PY_OPERATORS["!="]("Positive", "Negative") is True
    assert m.PY_OPERATORS["!="]("Positive", "positive") is False


def test_operator_in_case_insensitive():
    assert m.PY_OPERATORS["in"](1, [0, 1]) is True
    assert m.PY_OPERATORS["in"]("female", ["Female", "Male"]) is True
    assert m.PY_OPERATORS["in"](3, [0, 1]) is False


def test_operator_not_in():
    assert m.PY_OPERATORS["not_in"](3, [0, 1]) is True
    assert m.PY_OPERATORS["not_in"](1, [0, 1]) is False


def test_operator_in_with_non_list_target_is_false_not_crash():
    # "value" being a bare string instead of a list shouldn't crash -- just
    # means "not in" by definition.
    assert m.PY_OPERATORS["in"]("Positive", "Positive") is False


# ---------------------------------------------------------------------------
# check_python_rule: missing fields, bad operators, bad comparisons
# ---------------------------------------------------------------------------

def _rule(**kwargs):
    base = {"rule_id": "R1", "type": "inclusion", "field": "age",
            "operator": ">=", "value": 18}
    base.update(kwargs)
    return base


def test_check_python_rule_missing_field_is_unknown():
    patient = {"age": None}
    result, reason = m.check_python_rule(patient, _rule())
    assert result == "Unknown"
    assert "no value" in reason.lower()


def test_check_python_rule_field_absent_entirely_is_unknown():
    patient = {}
    result, reason = m.check_python_rule(patient, _rule())
    assert result == "Unknown"


def test_check_python_rule_unrecognized_operator_is_unknown():
    patient = {"age": 55}
    rule = _rule(operator="between")  # not a real operator
    result, reason = m.check_python_rule(patient, rule)
    assert result == "Unknown"
    assert "unrecognized operator" in reason.lower()


def test_check_python_rule_type_mismatch_is_unknown_not_crash():
    # comparing a string age against a numeric threshold with >= should not
    # raise -- it should be caught and reported as Unknown.
    patient = {"age": "not-a-number"}
    rule = _rule()
    result, reason = m.check_python_rule(patient, rule)
    assert result == "Unknown"
    assert "could not compare" in reason.lower()


# ---------------------------------------------------------------------------
# Inclusion vs exclusion polarity
# ---------------------------------------------------------------------------

def test_inclusion_condition_true_is_met():
    patient = {"age": 55}
    rule = _rule(type="inclusion", field="age", operator=">=", value=18)
    result, _ = m.check_python_rule(patient, rule)
    assert result == "Met"


def test_inclusion_condition_false_is_not_met():
    patient = {"age": 10}
    rule = _rule(type="inclusion", field="age", operator=">=", value=18)
    result, _ = m.check_python_rule(patient, rule)
    assert result == "Not Met"


def test_exclusion_condition_true_is_not_met():
    # exclusion rule: field/operator/value describe the DISQUALIFYING
    # condition, so condition True -> patient IS excluded -> Not Met.
    patient = {"brain_metastases": True}
    rule = _rule(type="exclusion", field="brain_metastases", operator="==", value=True)
    result, _ = m.check_python_rule(patient, rule)
    assert result == "Not Met"


def test_exclusion_condition_false_is_met():
    patient = {"brain_metastases": False}
    rule = _rule(type="exclusion", field="brain_metastases", operator="==", value=True)
    result, _ = m.check_python_rule(patient, rule)
    assert result == "Met"


# ---------------------------------------------------------------------------
# check_llm_rule: safe fallback when no API key is configured (no network
# call, so this test needs no API key and never costs anything)
# ---------------------------------------------------------------------------

def test_check_llm_rule_without_client_is_unknown():
    original_client = m._client
    try:
        m._client = None
        result, reason = m.check_llm_rule({"age": 55}, _rule(check_method="llm"))
        assert result == "Unknown"
        assert "not configured" in reason.lower()
    finally:
        m._client = original_client  # restore, don't leak state into other tests


# ---------------------------------------------------------------------------
# collapse_logic_groups: three-valued OR for alternative rules
# ---------------------------------------------------------------------------

def test_logic_group_met_beats_everything():
    results = [
        {"rule_id": "A", "type": "inclusion", "description": "ER+", "result": "Met", "reason": "", "logic_group": "OR_1"},
        {"rule_id": "B", "type": "inclusion", "description": "PR+", "result": "Not Met", "reason": "", "logic_group": "OR_1"},
    ]
    collapsed = m.collapse_logic_groups(results)
    assert len(collapsed) == 1
    assert collapsed[0]["result"] == "Met"


def test_logic_group_unknown_beats_not_met():
    results = [
        {"rule_id": "A", "type": "inclusion", "description": "ER+", "result": "Unknown", "reason": "", "logic_group": "OR_1"},
        {"rule_id": "B", "type": "inclusion", "description": "PR+", "result": "Not Met", "reason": "", "logic_group": "OR_1"},
    ]
    collapsed = m.collapse_logic_groups(results)
    assert collapsed[0]["result"] == "Unknown"


def test_logic_group_all_not_met_stays_not_met():
    results = [
        {"rule_id": "A", "type": "inclusion", "description": "ER+", "result": "Not Met", "reason": "", "logic_group": "OR_1"},
        {"rule_id": "B", "type": "inclusion", "description": "PR+", "result": "Not Met", "reason": "", "logic_group": "OR_1"},
    ]
    collapsed = m.collapse_logic_groups(results)
    assert collapsed[0]["result"] == "Not Met"


def test_standalone_rules_pass_through_unchanged():
    results = [
        {"rule_id": "A", "type": "inclusion", "description": "Age", "result": "Met", "reason": "", "logic_group": None},
    ]
    collapsed = m.collapse_logic_groups(results)
    assert len(collapsed) == 1
    assert collapsed[0]["rule_id"] == "A"


# ---------------------------------------------------------------------------
# summarize: counting + overall verdict logic
# ---------------------------------------------------------------------------

def _flat_result(result, logic_group=None):
    return {"rule_id": "R", "type": "inclusion", "description": "", "result": result, "reason": "", "logic_group": logic_group}


def test_summarize_all_met_is_likely_eligible():
    results = [_flat_result("Met"), _flat_result("Met")]
    summary = m.summarize(results)
    assert summary == {"met": 2, "not_met": 0, "unknown": 0, "not_applicable": 0, "overall": "Likely Eligible"}


def test_summarize_any_not_met_is_excluded():
    results = [_flat_result("Met"), _flat_result("Not Met"), _flat_result("Unknown")]
    summary = m.summarize(results)
    assert summary["overall"] == "Excluded"
    assert summary["not_met"] == 1


def test_summarize_unknown_without_not_met_is_needs_review():
    results = [_flat_result("Met"), _flat_result("Unknown")]
    summary = m.summarize(results)
    assert summary["overall"] == "Needs Review"


def test_summarize_not_applicable_excluded_from_counts():
    results = [_flat_result("Met"), _flat_result("Not Applicable")]
    summary = m.summarize(results)
    assert summary["met"] == 1
    assert summary["not_applicable"] == 1
    assert summary["overall"] == "Likely Eligible"  # NA doesn't block eligibility


# ---------------------------------------------------------------------------
# match_patient_to_trial: routes python vs llm, respects applies_if
# ---------------------------------------------------------------------------

def test_match_patient_to_trial_routes_python_rule_without_llm():
    patient = {"age": 55}
    trial = {"rules": [
        {"rule_id": "R1", "type": "inclusion", "rule_text": "Age 18+", "check_method": "python",
         "field": "age", "operator": ">=", "value": 18, "applies_if": None, "logic_group": None},
    ]}
    results = m.match_patient_to_trial(patient, trial)
    assert len(results) == 1
    assert results[0]["result"] == "Met"


def test_match_patient_to_trial_routes_applies_if_rule_to_llm_path():
    # Even though check_method is "python", an applies_if condition forces
    # the LLM path (which, with no client configured, safely returns
    # Unknown instead of crashing or guessing).
    original_client = m._client
    try:
        m._client = None
        patient = {"age": 55}
        trial = {"rules": [
            {"rule_id": "R1", "type": "inclusion", "rule_text": "cohort-specific rule",
             "check_method": "python", "field": "age", "operator": ">=", "value": 18,
             "applies_if": "patient is in cohort B", "logic_group": None},
        ]}
        results = m.match_patient_to_trial(patient, trial)
        assert results[0]["result"] == "Unknown"
    finally:
        m._client = original_client


# ---------------------------------------------------------------------------
# check_llm_rule: Claude answers about the CONDITION (Yes/No/Unknown) and the
# code converts it to Met/Not Met. A fake client is used, so no API calls.
# ---------------------------------------------------------------------------

class _FakeBlock:
    type = "text"
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    stop_reason = "end_turn"
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, text):
        self._text = text
    def create(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def _llm_result(rule_type, answer):
    original_client = m._client
    try:
        m._client = _FakeClient(f"ANSWER: {answer}\nREASON: test reason.")
        return m.check_llm_rule({"age": 55}, _rule(type=rule_type, check_method="llm"))[0]
    finally:
        m._client = original_client


def test_llm_exclusion_condition_absent_is_met():
    # e.g. "invasive breast cancer" -- patient has DCIS only -> passes the rule
    assert _llm_result("exclusion", "No") == "Met"


def test_llm_exclusion_condition_present_is_not_met():
    assert _llm_result("exclusion", "Yes") == "Not Met"


def test_llm_inclusion_condition_true_is_met():
    assert _llm_result("inclusion", "Yes") == "Met"


def test_llm_inclusion_condition_false_is_not_met():
    assert _llm_result("inclusion", "No") == "Not Met"


def test_llm_unknown_stays_unknown_for_both_rule_types():
    assert _llm_result("inclusion", "Unknown") == "Unknown"
    assert _llm_result("exclusion", "Unknown") == "Unknown"


def test_llm_not_applicable_is_passed_through():
    assert _llm_result("inclusion", "Not Applicable") == "Not Applicable"


if __name__ == "__main__":
    # Plain-assert runner so this file works even without pytest installed --
    # just `python3 test_agent2_matcher.py`.
    import traceback

    tests = [(name, obj) for name, obj in list(globals().items())
              if name.startswith("test_") and callable(obj)]
    passed, failed = 0, 0
    for name, test_fn in tests:
        try:
            test_fn()
            print(f"PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            failed += 1
        except Exception:
            print(f"ERROR {name}:")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(1 if failed else 0)
