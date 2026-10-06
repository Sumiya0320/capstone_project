"""
Agent 2: Matcher & Explainer

Compares one synthetic patient against one trial's structured rule list
AS PRODUCED BY AGENT 1 (the Gemini-based extractor in agent1/agent1.py),
and returns, for every rule, one of: Met / Not Met / Unknown / Not Applicable,
plus a one-line reason.

This version reads Agent 1's actual output format directly:
    {
      "trial_id": "...",
      "title": "...",
      "model": "...",
      "rules": [
        {
          "rule_id": "...",
          "type": "inclusion" | "exclusion",
          "rule_text": "...",
          "source_text": "...",
          "check_method": "python" | "llm",
          "field": "..." | null,
          "operator": ">=" | "<=" | ">" | "<" | "==" | "!=" | "in" | "not_in" | null,
          "value": <number | list | string> | null,
          "applies_if": "..." | null,
          "logic_group": "OR_1" | null,
          "notes": "..." | null
        },
        ...
      ]
    }

Hybrid approach (same spirit as before):
  - check_method "python" rules with a plain field/operator/value are checked
    with plain Python -- fast, free, 100% consistent, no AI involved.
  - check_method "llm" rules, and ANY rule that has an "applies_if" condition
    (since deciding whether a rule even applies requires reading free text),
    are sent to an LLM.
  - If a rule's required field is missing from the patient record, "python"
    rules return "Unknown" instead of guessing.

type (inclusion/exclusion) polarity:
  - inclusion: the stated condition must be TRUE for the patient to pass ->
    condition True => Met, False => Not Met.
  - exclusion: field/operator/value (or the LLM's reading of rule_text)
    describe the DISQUALIFYING condition -> condition True => Not Met
    (patient is excluded), False => Met (patient does not trigger the
    exclusion).

logic_group: rules sharing the same logic_group are alternatives (at least
one must hold). summarize() collapses each group into a single combined
result using three-valued OR (Met beats Unknown beats Not Met) before
counting Met/Not Met/Unknown for the overall summary.

If no API key is configured, "llm" rules fall back to "Unknown" with a note
explaining why, instead of crashing.

Usage:
    python agent2_matcher.py

Requires (only if you want the LLM path to actually run):
    pip install anthropic python-dotenv
    A .env file (NOT committed to git) containing:
        ANTHROPIC_API_KEY=your-key-here
"""

import json
import os

# --- LLM setup (optional; only needed for "llm" rules and applies_if rules) -
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed -- fine, we just won't auto-load a .env file

API_KEY = os.environ.get("ANTHROPIC_API_KEY")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=API_KEY) if API_KEY else None
except ImportError:
    _client = None


def get_nested(record: dict, dotted_field: str):
    """Support fields like 'biomarkers.HER2_status' against a nested dict."""
    if not dotted_field:
        return None
    value = record
    for part in dotted_field.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _norm(x):
    return x.strip().lower() if isinstance(x, str) else x


def _values_equal(a, b):
    return _norm(a) == _norm(b)


def _value_in(a, items):
    if not isinstance(items, (list, tuple, set)):
        return False
    return any(_values_equal(a, item) for item in items)


PY_OPERATORS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": _values_equal,
    "!=": lambda a, b: not _values_equal(a, b),
    "in": _value_in,
    "not_in": lambda a, b: not _value_in(a, b),
}


def _apply_polarity(rule_type, condition_true, base_reason):
    """inclusion: condition True -> Met. exclusion: condition True -> Not Met
    (the field/operator/value for an exclusion rule describe the
    DISQUALIFYING condition, per Agent 1's extraction convention)."""
    if rule_type == "exclusion":
        result = "Not Met" if condition_true else "Met"
    else:
        result = "Met" if condition_true else "Not Met"
    return result, base_reason


def check_python_rule(patient, rule):
    field = rule.get("field")
    field_value = get_nested(patient, field)
    if field_value is None:
        return "Unknown", f"Patient record has no value for '{field}'"

    op = rule.get("operator")
    target = rule.get("value")
    checker = PY_OPERATORS.get(op)
    if checker is None:
        return "Unknown", f"Unrecognized operator '{op}' -- needs manual review"

    try:
        condition_true = checker(field_value, target)
    except TypeError:
        return "Unknown", f"Could not compare {field}={field_value!r} {op} {target!r}"

    reason = f"{field} = {field_value!r}, condition '{op} {target!r}' is {condition_true}"
    return _apply_polarity(rule.get("type", "inclusion"), condition_true, reason)


def check_llm_rule(patient, rule):
    """Used for check_method == 'llm', and for ANY rule with an 'applies_if'
    condition (applicability needs to be read from free text too)."""
    if _client is None:
        return "Unknown", "LLM not configured (no ANTHROPIC_API_KEY set) -- needs manual review"

    applies_if_line = ""
    if rule.get("applies_if"):
        applies_if_line = f"\nThis rule only applies if: {rule['applies_if']}"

    prompt = f"""You are checking one clinical trial eligibility rule against one patient record.

Rule type: {rule.get('type', 'inclusion')} (inclusion = patient must satisfy it to be eligible;
exclusion = patient is ineligible if the condition described is true)
Rule (plain English): {rule.get('rule_text')}
Original trial text: {rule.get('source_text')}{applies_if_line}

Patient record (JSON):
{json.dumps(patient, indent=2)}

Decide the final eligibility outcome for this rule:
- Met: patient satisfies the trial's requirement for this rule
- Not Met: patient fails / is excluded by this rule
- Unknown: the patient record genuinely lacks the information needed to decide -- do not guess
- Not Applicable: only use this if an "applies_if" condition was given above and it does not apply to this patient

Respond with EXACTLY two lines, nothing else:
RESULT: <Met|Not Met|Unknown|Not Applicable>
REASON: <one short sentence>"""

    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        result_line = next(l for l in text.splitlines() if l.startswith("RESULT:"))
        reason_line = next(l for l in text.splitlines() if l.startswith("REASON:"))
        result = result_line.split("RESULT:", 1)[1].strip()
        reason = reason_line.split("REASON:", 1)[1].strip()
        return result, reason
    except Exception as e:
        return "Unknown", f"LLM call failed ({e}) -- needs manual review"


def match_patient_to_trial(patient: dict, trial: dict):
    results = []
    for rule in trial.get("rules", []):
        # Any rule with an applies_if condition needs language reasoning to
        # decide applicability, so it always goes through the LLM checker,
        # regardless of its own check_method.
        use_llm = rule.get("check_method") == "llm" or bool(rule.get("applies_if"))
        checker = check_llm_rule if use_llm else check_python_rule

        result, reason = checker(patient, rule)
        results.append({
            "rule_id": rule.get("rule_id"),
            "type": rule.get("type"),
            "description": rule.get("rule_text"),
            "result": result,
            "reason": reason,
            "logic_group": rule.get("logic_group"),
        })
    return results


def collapse_logic_groups(results):
    """Rules sharing a logic_group are alternatives (at least one must hold).
    Collapse each group into one combined result using three-valued OR:
    Met if any member is Met; else Unknown if any member is Unknown;
    else Not Met."""
    grouped = {}
    standalone = []
    for r in results:
        group = r.get("logic_group")
        if group:
            grouped.setdefault(group, []).append(r)
        else:
            standalone.append(r)

    collapsed = list(standalone)
    for group, members in grouped.items():
        outcomes = [m["result"] for m in members]
        if "Met" in outcomes:
            combined = "Met"
        elif "Unknown" in outcomes:
            combined = "Unknown"
        else:
            combined = "Not Met"
        collapsed.append({
            "rule_id": group,
            "type": members[0].get("type"),
            "description": "At least one of: " + "; ".join(m["description"] or "" for m in members),
            "result": combined,
            "reason": f"OR-group of {len(members)} alternative rule(s) -> {combined}",
            "logic_group": group,
        })
    return collapsed


def summarize(results):
    collapsed = collapse_logic_groups(results)
    counted = [r for r in collapsed if r["result"] != "Not Applicable"]
    met = sum(1 for r in counted if r["result"] == "Met")
    not_met = sum(1 for r in counted if r["result"] == "Not Met")
    unknown = sum(1 for r in counted if r["result"] == "Unknown")
    not_applicable = len(collapsed) - len(counted)
    overall = "Excluded" if not_met > 0 else ("Needs Review" if unknown > 0 else "Likely Eligible")
    return {
        "met": met, "not_met": not_met, "unknown": unknown,
        "not_applicable": not_applicable, "overall": overall,
    }


def _find_root(marker):
    """Walk up from the current directory looking for a folder/file named
    `marker`, so this script works no matter which folder you run it from."""
    path = os.getcwd()
    for _ in range(6):
        if os.path.exists(os.path.join(path, marker)):
            return path
        path = os.path.dirname(path)
    return None


if __name__ == "__main__":
    import glob

    root = _find_root("data/rules/raw") or os.getcwd()
    trial_dir = os.path.join(root, "data", "rules", "raw")

    patient_matches = glob.glob(os.path.join(root, "**", "synthetic_patients_simple.json"), recursive=True)
    if not patient_matches:
        print("Could not find synthetic_patients_simple.json anywhere under the project folder.")
        patients = []
    else:
        with open(patient_matches[0]) as f:
            patients = json.load(f)
        print(f"Loaded {len(patients)} patients from {patient_matches[0]}")

    trial_files = sorted(glob.glob(os.path.join(trial_dir, "*.json")))
    print(f"Found {len(trial_files)} trial files in {trial_dir}")

    trials = []
    for path in trial_files:
        with open(path) as f:
            trials.append(json.load(f, strict=False))

    if patients and trials:
        # Optional quick-test mode: set LIMIT_PATIENTS / LIMIT_TRIALS env vars
        # to run a small slice first, e.g.:
        #   LIMIT_PATIENTS=2 LIMIT_TRIALS=2 python3 agent2_matcher.py
        limit_patients = os.environ.get("LIMIT_PATIENTS")
        limit_trials = os.environ.get("LIMIT_TRIALS")
        if limit_patients:
            patients = patients[: int(limit_patients)]
        if limit_trials:
            trials = trials[: int(limit_trials)]

        total = len(patients) * len(trials)
        print(f"\nChecking {len(patients)} patients x {len(trials)} trials = {total} combinations...")
        print("(tip: for a quick test run, use LIMIT_PATIENTS=2 LIMIT_TRIALS=2 python3 agent2_matcher.py)\n")

        out_path = os.path.join(root, "match_results.csv")
        fieldnames = ["patient_id", "trial_id", "met", "not_met", "unknown", "not_applicable", "overall"]

        import csv
        import time
        start = time.time()
        rows = []
        done = 0

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p_idx, patient in enumerate(patients, 1):
                print(f"  [{p_idx}/{len(patients)}] {patient['patient_id']} ...", flush=True)
                for trial in trials:
                    results = match_patient_to_trial(patient, trial)
                    summary = summarize(results)
                    row = {"patient_id": patient["patient_id"], "trial_id": trial["trial_id"], **summary}
                    rows.append(row)
                    writer.writerow(row)
                    f.flush()  # so match_results.csv fills in live, even if the run is stopped early
                    done += 1

        elapsed = time.time() - start
        print(f"\nDone: {done} combinations checked in {elapsed:.0f}s -> saved to {out_path}")

        try:
            import pandas as pd
            df = pd.DataFrame(rows)
            print(f"\n{df.to_string(index=False)}")
        except ImportError:
            for row in rows:
                print(" ", row)
    else:
        print("Nothing to match -- check that patients and trial files were found above.")
