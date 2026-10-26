"""
Agent 2: Matcher & Explainer

Compares one synthetic patient against one trial's structured rule list
as produced by Agent 1.

For every rule, Agent 2 returns one of:

    Met
    Not Met
    Unknown
    Not Applicable

plus a short explanation.

Expected Agent 1 format:

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
        }
    ]
}

Hybrid approach:

- Simple structured rules are evaluated directly with Python.
- Complex natural-language rules are evaluated with Claude (Anthropic API).
- Rules with applies_if are evaluated with Claude (Anthropic API).
- Claude only answers whether the rule condition is true (Yes/No/Unknown);
  the code converts that into Met/Not Met, so exclusion logic is never
  left to the model.
- Missing patient information produces Unknown rather than a guess.
- API failures are explicitly marked so they are not confused with
  genuine patient-data gaps.

Eligibility semantics:

INCLUSION
    Condition true  -> Met
    Condition false -> Not Met

EXCLUSION
    Disqualifying condition true  -> Not Met
    Disqualifying condition false -> Met

Missing evidence never automatically means a rule is satisfied or failed.
"""

import csv
import glob
import json
import os
import time
import traceback

from dotenv import load_dotenv
import anthropic


# ============================================================
# Claude (Anthropic API) setup
# ============================================================

load_dotenv()

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("AGENT2_MODEL", "claude-haiku-4-5-20251001")

_client = anthropic.Anthropic(api_key=API_KEY) if API_KEY else None


# Retry settings for temporary API failures
LLM_MAX_RETRIES = 5
LLM_BASE_DELAY = 5


# ============================================================
# General helpers
# ============================================================

def get_nested(record: dict, dotted_field: str):
    """
    Support fields such as:

        biomarkers.HER2_status

    against nested patient dictionaries.
    """

    if not dotted_field:
        return None

    value = record

    for part in dotted_field.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None

    return value


def _norm(value):
    """Normalize strings for case-insensitive comparisons."""

    if isinstance(value, str):
        return value.strip().lower()

    return value


def _values_equal(a, b):
    """Case-insensitive equality for strings."""

    return _norm(a) == _norm(b)


def _value_in(a, items):
    """Check whether a value occurs in a list/tuple/set."""

    if not isinstance(items, (list, tuple, set)):
        return False

    return any(
        _values_equal(a, item)
        for item in items
    )


# ============================================================
# Python operators
# ============================================================

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


# ============================================================
# Eligibility polarity
# ============================================================

def _apply_polarity(
    rule_type,
    condition_true,
    base_reason
):
    """
    Convert the truth value of a rule condition into an
    eligibility result.

    Inclusion:
        condition True  -> Met
        condition False -> Not Met

    Exclusion:
        condition True  -> Not Met
        condition False -> Met

    For exclusion criteria, the condition describes the
    disqualifying condition.
    """

    if rule_type == "exclusion":
        result = (
            "Not Met"
            if condition_true
            else "Met"
        )

    else:
        result = (
            "Met"
            if condition_true
            else "Not Met"
        )

    return result, base_reason


# ============================================================
# Python rule checker
# ============================================================

def check_python_rule(patient, rule):
    """
    Evaluate a simple structured eligibility rule using Python.
    """

    field = rule.get("field")

    field_value = get_nested(
        patient,
        field
    )

    # Missing information should never be guessed
    if field_value is None:
        return (
            "Unknown",
            f"Patient record has no value for '{field}'"
        )

    operator = rule.get("operator")
    target = rule.get("value")

    checker = PY_OPERATORS.get(operator)

    if checker is None:
        return (
            "Unknown",
            (
                f"Unrecognized operator '{operator}' "
                "-- needs manual review"
            )
        )

    try:
        condition_true = checker(
            field_value,
            target
        )

    except TypeError:
        return (
            "Unknown",
            (
                f"Could not compare "
                f"{field}={field_value!r} "
                f"{operator} {target!r}"
            )
        )

    reason = (
        f"{field} = {field_value!r}, "
        f"condition '{operator} {target!r}' "
        f"is {condition_true}"
    )

    return _apply_polarity(
        rule.get(
            "type",
            "inclusion"
        ),
        condition_true,
        reason
    )

def check_required_input_rule(patient, rule):
    """
    Handle exclusion rules of the form:

        Required DCISionRT input 'age' is missing
        Required DCISionRT input 'tumor size' is missing
        Required DCISionRT input 'margin status' is missing
        Required DCISionRT input 'palpability' is missing

    If the value is present in the patient record, the exclusion
    is not triggered -> Met.

    If the value is absent, we do not assume the real clinical
    input is missing -> Unknown.
    """

    text = rule.get("rule_text", "").lower()

    field_map = {
        "age": "age",
        "tumor size": "tumor_size",
        "margin status": "margin_status",
        "palpability": "palpability",
    }

    for label, field in field_map.items():

        if (
            "required dcisionrt input" in text
            and label in text
            and "missing" in text
        ):

            value = get_nested(patient, field)

            if value is None:
                return (
                    "Unknown",
                    (
                        f"{label.title()} is not documented in the "
                        "patient record, so it cannot be confirmed "
                        "whether the required DCISionRT input is missing."
                    )
                )

            return (
                "Met",
                (
                    f"{label.title()} is documented in the "
                    "patient record, so the required DCISionRT "
                    "input is not missing."
                )
            )

    return None

# ============================================================
# LLM rule checker
# ============================================================

def check_llm_rule(patient, rule):
    """
    Evaluate a complex natural-language eligibility rule.

    This function is used when:

    - check_method == "llm"
    - the rule contains an applies_if condition

    Missing information must return Unknown rather than being
    treated as evidence for or against eligibility.
    """

    if _client is None:
        return (
            "Unknown",
            (
                "LLM not configured "
                "(no ANTHROPIC_API_KEY set) "
                "-- needs manual review"
            )
        )

    applies_if_line = ""

    if rule.get("applies_if"):
        applies_if_line = (
            "\nThis rule only applies if: "
            f"{rule['applies_if']}"
        )

    prompt = f"""
You are checking one clinical trial eligibility rule against one patient record.

Rule type:
{rule.get("type", "inclusion")}

Rule (the condition to check):
{rule.get("rule_text")}

Original trial wording:
{rule.get("source_text")}
{applies_if_line}

Patient record:
{json.dumps(patient, indent=2)}

QUESTION:
Based only on the patient record, is the condition stated in the Rule TRUE for this patient?

Answer about the CONDITION, not about eligibility.
For an exclusion rule, the Rule describes the disqualifying condition, so answer whether
the patient HAS that condition. Do not convert your answer into Met or Not Met; the program
does that afterwards.

Yes
= the patient record positively supports that the condition is true.

No
= the patient record positively supports that the condition is false.

Unknown
= the patient record does not contain enough information to decide.

Not Applicable
= use only when an applies_if condition exists and the record clearly shows it does not apply.


IMPORTANT SAFETY AND LOGIC RULES:

- Use only facts explicitly supported by the patient record.
- Never invent diagnoses, procedures, dates, test results, treatment history, or other clinical information.
- Missing information is evidence of nothing: if the record neither confirms nor rules out the condition, answer Unknown.
- Never assume a condition is absent because it is not documented.
- Never assume a condition is present because supporting information is missing.
- Do not infer reproductive potential solely from age or menopausal status.
- Distinguish CURRENT disease from PRIOR medical history.
- A current diagnosis is not evidence of a prior diagnosis unless the record explicitly describes previous or historical disease.
- Words such as "prior", "previous", "history of", "formerly", or "past" require evidence about the patient's past history.
- If the record only documents the current diagnosis and gives no information about prior disease history, answer Unknown for a condition about prior disease.


EXAMPLE 1:

Exclusion rule:
"Patient tissue is insufficient to generate test results."

Patient record:
No tissue adequacy information is documented.

Correct:
ANSWER: Unknown
REASON: The record contains no information about tissue sufficiency.

Incorrect:
ANSWER: Yes
REASON: Tissue sufficiency is not documented.


EXAMPLE 2:

Exclusion rule:
"Patient has prior in situ or invasive breast cancer."

Patient record:
Current diagnosis is ductal carcinoma in situ (DCIS). No previous breast cancer history is documented.

Correct:
ANSWER: Unknown
REASON: The record documents current DCIS but does not say whether the patient has any prior breast cancer.

Incorrect:
ANSWER: Yes
REASON: The patient currently has DCIS.


Respond with EXACTLY two lines and nothing else:

ANSWER: <Yes|No|Unknown|Not Applicable>
REASON: <one short sentence describing the evidence about the condition>
""".strip()

    last_error = None

    for attempt in range(
        1,
        LLM_MAX_RETRIES + 1
    ):

        try:

            response = _client.messages.create(
                model=MODEL,
                max_tokens=400,
                system=(
                    "You are a clinical trial eligibility assessment assistant. "
                    "You decide whether a stated condition is true for a patient, "
                    "using only the provided patient record. "
                    "Answer about the condition itself, never about eligibility. "
                    "Missing information means Unknown. "
                    "Do not invent missing information. "
                    "Do not confuse a current diagnosis with prior medical history. "
                    "Respond in exactly two lines:\n"
                    "ANSWER: Yes|No|Unknown|Not Applicable\n"
                    "REASON: A short explanation."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            text = "".join(
                block.text
                for block in response.content
                if block.type == "text"
            ).strip()

            # --------------------------------------------
            # Detect incomplete output
            # --------------------------------------------

            if response.stop_reason == "max_tokens":
                raise ValueError(
                    "Claude response reached its "
                    "max_tokens limit."
                )

            if not text:
                raise ValueError(
                    (
                        "Claude returned an empty response. "
                        f"stop_reason={response.stop_reason}"
                    )
                )

            # --------------------------------------------
            # Parse ANSWER and REASON
            # --------------------------------------------

            lines = [line.strip() for line in text.splitlines()]

            answer_line = next(
                (line for line in lines if line.upper().startswith("ANSWER:")),
                None
            )

            reason_line = next(
                (line for line in lines if line.upper().startswith("REASON:")),
                None
            )

            if answer_line is None or reason_line is None:
                raise ValueError(
                    "Unexpected Claude response "
                    f"format: {text[:300]!r}"
                )

            answer = (
                answer_line.split(":", 1)[1]
                .strip()
                .strip(".")
                .lower()
            )

            reason = reason_line.split(":", 1)[1].strip()

            if not reason:
                raise ValueError("Missing eligibility explanation")

            # --------------------------------------------
            # Convert the condition answer into an
            # eligibility result, exactly like the
            # Python checks do (see _apply_polarity).
            # --------------------------------------------

            if answer in ("yes", "no"):
                return _apply_polarity(
                    rule.get("type", "inclusion"),
                    answer == "yes",
                    reason
                )

            if answer == "unknown":
                return "Unknown", reason

            if answer in ("not applicable", "n/a"):
                return "Not Applicable", reason

            raise ValueError(f"Invalid answer: {answer!r}")

        except Exception as error:

            last_error = error

            print(
                f"ERROR TYPE: "
                f"{type(error).__name__}"
            )

            print(
                f"ERROR DETAILS: "
                f"{repr(error)}"
            )

            traceback.print_exc()

            # --------------------------------------------
            # Retry temporary API errors only
            # --------------------------------------------

            status_code = getattr(
                error,
                "status_code",
                None
            )

            error_text = str(
                error
            ).lower()

            is_transient = (
                status_code
                in (
                    429,
                    500,
                    502,
                    503,
                    529
                )
                or "rate" in error_text
                or "timeout" in error_text
                or "connection" in error_text
                or "overloaded" in error_text
            )

            if (
                not is_transient
                or attempt == LLM_MAX_RETRIES
            ):
                break

            delay = (
                LLM_BASE_DELAY
                * (2 ** (attempt - 1))
            )

            print(
                (
                    f"[rule {rule.get('rule_id')}: "
                    f"LLM call failed "
                    f"(attempt "
                    f"{attempt}/{LLM_MAX_RETRIES}): "
                    f"{error} -- "
                    f"retrying in {delay}s]"
                ),
                flush=True
            )

            time.sleep(delay)

    # ========================================================
    # All retries exhausted / non-transient failure
    # ========================================================

    print(
        (
            f"[rule {rule.get('rule_id')}: "
            f"LLM call FAILED after "
            f"{attempt} attempt(s): "
            f"{last_error}]"
        ),
        flush=True
    )

    return (
        "Unknown",
        (
            "[API ERROR -- not a real data gap] "
            f"LLM call failed: {last_error}"
        )
    )


# ============================================================
# Match one patient against one trial
# ============================================================

def match_patient_to_trial(
    patient: dict,
    trial: dict
):
    """
    Evaluate every eligibility rule for one patient.
    """

    results = []

    for rule in trial.get("rules", []):

        special_result = check_required_input_rule(
            patient,
            rule
        )

        if special_result is not None:

            result, reason = special_result

        else:

            use_llm = (
                rule.get("check_method") == "llm"
                or bool(rule.get("applies_if"))
            )

            checker = (
                check_llm_rule
                if use_llm
                else check_python_rule
            )

            result, reason = checker(
                patient,
                rule
            )

        results.append(
            {
                "rule_id": rule.get("rule_id"),
                "type": rule.get("type"),
                "description": rule.get("rule_text"),
                "result": result,
                "reason": reason,
                "logic_group": rule.get("logic_group"),
            }
        )
    return results


# ============================================================
# Logic-group processing
# ============================================================

def collapse_logic_groups(results):
    """
    Combine alternative eligibility conditions.

    Inclusion alternatives:
        Any Met -> Met

    Exclusion alternatives:
        Any Not Met -> Not Met

    Unknown means insufficient information.

    Not Applicable does not determine the group's result.
    """

    grouped = {}
    standalone = []

    for rule in results:

        group = rule.get(
            "logic_group"
        )

        if group:
            grouped.setdefault(
                group,
                []
            ).append(rule)

        else:
            standalone.append(rule)

    collapsed = list(
        standalone
    )

    for group, members in grouped.items():

        rule_types = {
            member.get("type")
            for member in members
        }

        if len(rule_types) != 1:
            raise ValueError(
                (
                    "Mixed rule types in "
                    f"logic group {group}"
                )
            )

        rule_type = next(
            iter(rule_types)
        )

        outcomes = [
            member["result"]
            for member in members
        ]

        valid_outcomes = {
            "Met",
            "Not Met",
            "Unknown",
            "Not Applicable"
        }

        if any(
            outcome not in valid_outcomes
            for outcome in outcomes
        ):
            raise ValueError(
                (
                    "Invalid result in "
                    f"logic group {group}"
                )
            )

        # ----------------------------------------------------
        # Exclusion alternatives
        # ----------------------------------------------------

        if rule_type == "exclusion":

            # One triggered exclusion is enough to fail group
            if "Not Met" in outcomes:
                combined = "Not Met"

            elif "Unknown" in outcomes:
                combined = "Unknown"

            elif "Met" in outcomes:
                combined = "Met"

            else:
                combined = "Not Applicable"

        # ----------------------------------------------------
        # Inclusion alternatives
        # ----------------------------------------------------

        elif rule_type == "inclusion":

            # One satisfied alternative is enough
            if "Met" in outcomes:
                combined = "Met"

            elif "Unknown" in outcomes:
                combined = "Unknown"

            elif "Not Met" in outcomes:
                combined = "Not Met"

            else:
                combined = "Not Applicable"

        else:
            raise ValueError(
                (
                    "Invalid rule type in "
                    f"group {group}"
                )
            )

        collapsed.append(
            {
                "rule_id": group,
                "type": rule_type,
                "description": (
                    "Grouped eligibility conditions"
                ),
                "result": combined,
                "reason": (
                    f"Combined {len(members)} "
                    f"alternative {rule_type} "
                    "conditions."
                ),
                "logic_group": group,
            }
        )

    return collapsed


# ============================================================
# Eligibility summary
# ============================================================

def summarize(results):
    """
    Produce overall eligibility counts and preliminary outcome.
    """

    collapsed = collapse_logic_groups(
        results
    )

    counted = [
        rule
        for rule in collapsed
        if rule["result"] != "Not Applicable"
    ]

    met = sum(
        1
        for rule in counted
        if rule["result"] == "Met"
    )

    not_met = sum(
        1
        for rule in counted
        if rule["result"] == "Not Met"
    )

    unknown = sum(
        1
        for rule in counted
        if rule["result"] == "Unknown"
    )

    not_applicable = (
        len(collapsed)
        - len(counted)
    )

    if not_met > 0:
        overall = "Excluded"

    elif unknown > 0:
        overall = "Needs Review"

    else:
        overall = "Likely Eligible"

    return {
        "met": met,
        "not_met": not_met,
        "unknown": unknown,
        "not_applicable": not_applicable,
        "overall": overall,
    }


# ============================================================
# Standalone testing helpers
# ============================================================

def _find_root(marker):
    """
    Walk up from the current directory looking for a
    folder/file named marker.

    This allows the script to run from different directories.
    """

    path = os.getcwd()

    for _ in range(6):

        if os.path.exists(
            os.path.join(
                path,
                marker
            )
        ):
            return path

        path = os.path.dirname(
            path
        )

    return None


# ============================================================
# Standalone execution
# ============================================================

if __name__ == "__main__":

    # Prefer newer draft rules if present.
    root = (
        _find_root(
            "data/rules/drafts"
        )
        or _find_root(
            "data/rules/raw"
        )
        or os.getcwd()
    )

    drafts_dir = os.path.join(
        root,
        "data",
        "rules",
        "drafts"
    )

    raw_dir = os.path.join(
        root,
        "data",
        "rules",
        "raw"
    )

    # --------------------------------------------------------
    # Find synthetic patient data
    # --------------------------------------------------------

    patient_matches = glob.glob(
        os.path.join(
            root,
            "**",
            "synthetic_patients_simple.json"
        ),
        recursive=True
    )

    if not patient_matches:

        print(
            (
                "Could not find "
                "synthetic_patients_simple.json "
                "anywhere under the project folder."
            )
        )

        patients = []

    else:

        with open(
            patient_matches[0],
            "r",
            encoding="utf-8"
        ) as file:
            patients = json.load(file)

        print(
            (
                f"Loaded {len(patients)} "
                f"patients from "
                f"{patient_matches[0]}"
            )
        )

    # --------------------------------------------------------
    # Load rule files
    # --------------------------------------------------------

    trial_files = []

    # Prefer drafts
    if os.path.isdir(
        drafts_dir
    ):
        trial_files.extend(
            sorted(
                glob.glob(
                    os.path.join(
                        drafts_dir,
                        "*.json"
                    )
                )
            )
        )

    # Add raw files that do not already exist as drafts
    draft_ids = {
        os.path.basename(path)
        for path in trial_files
    }

    if os.path.isdir(
        raw_dir
    ):

        for path in sorted(
            glob.glob(
                os.path.join(
                    raw_dir,
                    "*.json"
                )
            )
        ):

            if (
                os.path.basename(path)
                not in draft_ids
            ):
                trial_files.append(path)

    print(
        (
            f"Found {len(trial_files)} "
            "Agent 1 rule file(s)."
        )
    )

    trials = []

    for path in trial_files:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            trials.append(
                json.load(
                    file,
                    strict=False
                )
            )

    # --------------------------------------------------------
    # Run batch test
    # --------------------------------------------------------

    if patients and trials:

        limit_patients = os.environ.get(
            "LIMIT_PATIENTS"
        )

        limit_trials = os.environ.get(
            "LIMIT_TRIALS"
        )

        if limit_patients:
            patients = patients[
                :int(limit_patients)
            ]

        if limit_trials:
            trials = trials[
                :int(limit_trials)
            ]

        total = (
            len(patients)
            * len(trials)
        )

        print(
            (
                f"\nChecking "
                f"{len(patients)} patients "
                f"x {len(trials)} trials "
                f"= {total} combinations...\n"
            )
        )

        out_path = os.path.join(
            root,
            "match_results.csv"
        )

        fieldnames = [
            "patient_id",
            "trial_id",
            "met",
            "not_met",
            "unknown",
            "not_applicable",
            "overall",
        ]

        start = time.time()

        rows = []
        done = 0

        with open(
            out_path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            for patient_index, patient in enumerate(
                patients,
                1
            ):

                print(
                    (
                        f"[{patient_index}/"
                        f"{len(patients)}] "
                        f"{patient.get('patient_id', 'Unknown')}"
                    ),
                    flush=True
                )

                for trial in trials:

                    results = (
                        match_patient_to_trial(
                            patient,
                            trial
                        )
                    )

                    summary = summarize(
                        results
                    )

                    row = {
                        "patient_id": patient.get(
                            "patient_id",
                            "Unknown"
                        ),
                        "trial_id": trial.get(
                            "trial_id",
                            "Unknown"
                        ),
                        **summary,
                    }

                    rows.append(row)

                    writer.writerow(
                        row
                    )

                    file.flush()

                    done += 1

        elapsed = (
            time.time()
            - start
        )

        print(
            (
                f"\nDone: {done} combinations "
                f"checked in {elapsed:.0f}s "
                f"-> saved to {out_path}"
            )
        )

        # Optional pretty dataframe display
        try:

            import pandas as pd

            dataframe = pd.DataFrame(
                rows
            )

            print(
                "\n"
                + dataframe.to_string(
                    index=False
                )
            )

        except ImportError:

            for row in rows:
                print(
                    row
                )

    else:

        print(
            (
                "Nothing to match -- "
                "check that patient and "
                "Agent 1 rule files were found."
            )
        )