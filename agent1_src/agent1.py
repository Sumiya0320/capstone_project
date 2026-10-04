"""Agent 1 (Gemini version): reads a trial's eligibility text and saves it as a list of rules (JSON).

Run from the repo root:
    python agent1/agent1.py data/trials/NCT05950945.json    # one trial
    python agent1/agent1.py --all                           # every trial in data/trials/
Output: data/rules/raw/<trial_id>.json
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "rules" / "raw"
MODEL = os.getenv("AGENT1_MODEL", "gemini-3.8-flash")  # change in .env if this model name stops working

# Edit this list so the names match the keys in your synthetic patient JSON.
PATIENT_FIELDS = ("age, sex, ecog, lvef_percent, life_expectancy_weeks, prior_metastatic_lines, "
                  "hormone_receptor_status, her2_status, brain_metastases")

PROMPT = f"""You convert a clinical trial's eligibility criteria into a flat list of simple, checkable rules.
Another agent will later compare a patient to each rule and answer Met / Not Met / Unknown.

Rules for extraction:
1. One condition per rule. Split compound sentences. Never drop, merge or invent criteria.
2. type: "inclusion" = patient must satisfy it; "exclusion" = patient is ineligible if it is true.
   Decide by meaning, not wording ("Was never previously treated with X" is an inclusion).
   For exclusion rules, rule_text/operator/value describe the DISQUALIFYING condition, not its opposite.
3. source_text: copy the exact words from the criteria. No paraphrasing.
4. rule_text: a short plain-English version of the rule.
5. check_method: "python" only for a simple comparison on ONE patient value (age, ECOG, LVEF, number of prior
   lines...) where the threshold is stated in the text. Everything else is "llm".
6. field/operator/value: fill in for python rules, otherwise null. Operators: >=, <=, >, <, ==, !=, in, not_in.
   value is always written as JSON text: 18 -> "18", 0 or 1 -> "[0, 1]", a word -> "\\"female\\"".
   Preferred field names: {PATIENT_FIELDS}.
7. Copy numbers, units and time windows exactly (>= is not >). Keep time windows in rule_text.
   Never invent a threshold. Vague criteria such as "adequate organ function" are still rules:
   check_method "llm", and say in notes that no threshold is given.
8. applies_if: the condition for conditional rules (e.g. a cohort). logic_group: a short id such as "OR_1"
   shared by rules that are alternatives (at least one must hold). Otherwise null.
9. Add an age rule from the minimum/maximum age lines (skip maximum if N/A) and a sex rule unless sex is ALL.
   Use the header line as source_text, e.g. "Minimum age: 18 Years".
10. Keep administrative items too (consent, contraception agreement) with check_method "llm".

Example: "Has an ECOG performance status of 0 or 1." ->
{{"type":"inclusion","rule_text":"ECOG 0 or 1","source_text":"Has an ECOG performance status of 0 or 1.","check_method":"python","field":"ecog","operator":"in","value":"[0, 1]","applies_if":null,"logic_group":null,"notes":null}}
Example: "Prior treatment with an antibody drug conjugate." ->
{{"type":"exclusion","rule_text":"Prior antibody drug conjugate treatment","source_text":"Prior treatment with an antibody drug conjugate.","check_method":"llm","field":null,"operator":null,"value":null,"applies_if":null,"logic_group":null,"notes":null}}
"""

S = types.Schema
T = types.Type


def text(nullable=True):
    return S(type=T.STRING, nullable=nullable)


RULE = S(
    type=T.OBJECT,
    properties={
        "type": S(type=T.STRING, enum=["inclusion", "exclusion"]),
        "rule_text": text(False),
        "source_text": text(False),
        "check_method": S(type=T.STRING, enum=["python", "llm"]),
        "field": text(),
        "operator": text(),
        "value": text(),
        "applies_if": text(),
        "logic_group": text(),
        "notes": text(),
    },
    required=["type", "rule_text", "source_text", "check_method"],
)
SCHEMA = S(type=T.OBJECT, properties={"rules": S(type=T.ARRAY, items=RULE)}, required=["rules"])


def as_text(x):
    return "\n".join(x) if isinstance(x, list) else str(x)


def extract_rules(client, trial):
    e = trial["eligibility"]
    criteria = (f"Minimum age: {e['minimum_age']}\nMaximum age: {e['maximum_age']}\nSex: {e['sex']}\n\n"
                f"INCLUSION CRITERIA\n{as_text(e['inclusion_criteria'])}\n\n"
                f"EXCLUSION CRITERIA\n{as_text(e['exclusion_criteria'])}")
    resp = client.models.generate_content(
        model=MODEL,
        contents=criteria,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0,
            max_output_tokens=16000,
        ),
    )
    return criteria, json.loads(resp.text)["rules"]


def run_trial(client, path):
    # strict=False because the criteria strings contain raw newlines
    trial = json.loads(Path(path).read_text(encoding="utf-8"), strict=False)
    trial_id = trial["trial_id"]
    criteria, rules = extract_rules(client, trial)

    flat = re.sub(r"\s+", " ", criteria)
    for i, r in enumerate(rules, 1):
        r["rule_id"] = f"{trial_id}_{i:02d}"
        for k in ("field", "operator", "value", "applies_if", "logic_group", "notes"):
            r.setdefault(k, None)
        if isinstance(r["value"], str):  # turn "18" / "[0, 1]" back into a number / list
            try:
                r["value"] = json.loads(r["value"])
            except ValueError:
                pass
        if re.sub(r"\s+", " ", r["source_text"]) not in flat:
            print(f"  WARNING {r['rule_id']}: source_text is not an exact copy of the trial text")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{trial_id}.json"
    out.write_text(json.dumps({"trial_id": trial_id, "title": trial["official_title"], "model": MODEL,
                               "rules": rules}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{trial_id}: saved {len(rules)} rules -> {out}")


if __name__ == "__main__":
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY not found. Put it in a .env file.")
    if len(sys.argv) < 2:
        sys.exit("usage: python agent1/agent1.py <trial.json> | --all")
    paths = sorted((ROOT / "data" / "trials").glob("*.json")) if sys.argv[1] == "--all" else [sys.argv[1]]
    client = genai.Client(api_key=key)
    for p in paths:
        try:
            run_trial(client, p)
        except Exception as err:
            print(f"{Path(p).name}: ERROR {err}")
