
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Project configuration
ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "rules" / "drafts"

load_dotenv(ROOT / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
client = OpenAI()


def extract_rules(trial):
    """
    Extract structured eligibility rules from a clinical trial.

    Input: trial dictionary from Clinical Trial Search
    Output: Agent 1-compatible JSON dictionary
    """

    trial_id = trial.get("nct_id") or trial.get("trial_id")
    title = trial.get("title", "Unknown Trial")
    criteria = trial.get("eligibility_criteria", "")

    if not trial_id or not re.fullmatch(r"NCT\d{8}", trial_id):
        raise ValueError("A valid NCT trial ID is required.")

    if not criteria or criteria == "Eligibility criteria not available.":
        raise ValueError("Trial eligibility criteria are missing.")

    prompt = f"""
Extract all inclusion and exclusion eligibility criteria
from the clinical trial below.

Return a JSON object containing a "rules" array.

Each rule must contain:
- type: inclusion or exclusion
- rule_text: simplified eligibility requirement
- source_text: exact supporting text from the trial
- check_method: python or llm
- field: patient field name or null
- operator: comparison operator or null
- value: comparison value or null
- applies_if: conditional applicability or null
- logic_group: shared ID for alternative conditions or null
- notes: extraction notes or null

Requirements:
1. Extract inclusion and exclusion criteria.
2. Do not invent clinical information.
3. Separate independent conditions into individual rules.
4. Preserve exact thresholds and clinical meaning.
5. Use python only for simple field comparisons.
6. Use llm for complex clinical requirements.
7. For exclusions, describe the disqualifying condition.
8. Identify conditional criteria using applies_if.
9. Preserve exact supporting text in source_text.
10. If a criterion is ambiguous, explain that in notes.
11. For Python checks, only use these operators:
    >=, <=, >, <, ==, !=, in, not_in.

12. Never use unsupported operators such as
    "is null", "contains", or "exists".

13. If a clinical requirement cannot be represented
    accurately with a supported Python operator,
    use check_method "llm".

14. Missing patient information must not automatically
    be interpreted as a confirmed clinical exclusion.

15. For exclusion conditions joined by OR, assign
    a shared logic_group identifier.

16. For inclusion alternatives joined by OR, assign
    a shared logic_group identifier.

17. Do not place unrelated requirements in the
    same logic_group.

Preferred patient fields:
age, sex, ecog, lvef_percent, life_expectancy_weeks,
prior_metastatic_lines, hormone_receptor_status,
her2_status, brain_metastases, menopausal_status.

Trial ID: {trial_id}
Trial Title: {title}

Minimum Age: {trial.get("minimum_age")}
Maximum Age: {trial.get("maximum_age")}
Sex: {trial.get("sex")}

Eligibility Criteria:
{criteria}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract clinical trial eligibility rules. "
                    "Return valid JSON only. "
                    "Never invent eligibility requirements."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=12000,
    )

    if response.choices[0].finish_reason != "stop":
        raise ValueError("OpenAI did not finish generating the rules.")

    content = response.choices[0].message.content

    if not content:
        raise ValueError("OpenAI returned an empty response.")

    extracted = json.loads(content)
    rules = extracted.get("rules")

    if not isinstance(rules, list) or not rules:
        raise ValueError("No valid eligibility rules were extracted.")

    required = {"type", "rule_text", "source_text", "check_method"}
    VALID_OPERATORS = {
        ">=", "<=", ">", "<",
        "==", "!=", "in", "not_in"
    }

    for index, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise ValueError(f"Rule {index} is not an object.")

        if not required.issubset(rule):
            raise ValueError(f"Rule {index} is missing required fields.")

        if rule["type"] not in ("inclusion", "exclusion"):
            raise ValueError(f"Invalid rule type at {index}.")

        if rule["check_method"] not in ("python", "llm"):
            raise ValueError(f"Invalid check method at {index}.")

        rule["rule_id"] = f"{trial_id}_{index:02d}"

        for key in (
            "field", "operator", "value",
            "applies_if", "logic_group", "notes"
        ):
            rule.setdefault(key, None)
        # Validate Python-based eligibility rules
        if rule["check_method"] == "python":

            operator = rule.get("operator")
            field = rule.get("field")
            value = rule.get("value")

            invalid_rule = (
                operator not in VALID_OPERATORS
                or not isinstance(field, str)
                or not field.strip()
                or value is None
            )

            if invalid_rule:
                rule["check_method"] = "llm"
                rule["field"] = None
                rule["operator"] = None
                rule["value"] = None

                rule["notes"] = (
                    str(rule.get("notes") or "")
                    + " Automatically flagged for manual review: "
                    "unsupported or incomplete Python comparison."
                ).strip()
        # Check whether supporting text occurs in the source.
        source = " ".join(str(rule["source_text"]).split())
        original = " ".join(criteria.split())

        if source not in original:
            rule["notes"] = (
                str(rule.get("notes") or "")
                + " WARNING: Source text needs manual verification."
            ).strip()

    return {
        "trial_id": trial_id,
        "title": title,
        "model": MODEL,
        "rules": rules,
    }


def save_draft_rules(output):
    """
    Save extracted rules for human review.
    Drafts are not used automatically by Agent 2.
    """

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)

    trial_id = output["trial_id"]
    output_path = DRAFT_DIR / f"{trial_id}.json"

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return output_path
