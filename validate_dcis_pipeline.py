"""Run live DCIS validation: python validate_dcis_pipeline.py.

Uses the connector's saved Agent 1 rules and real Agent 2 LLM calls;
requires OPENAI_API_KEY and network access. No rules or results are mocked.
The cases differ by the age cutoff or undocumented consent capacity.
"""

import json
from pathlib import Path

from integration.agent_connector import run_full_pipeline


ROOT = Path(__file__).resolve().parent
TRIAL_ID = "NCT04916808"
EXPECTED = {
    "SYN-DCIS-ELIGIBLE": "Likely Eligible",
    "SYN-DCIS-EXCLUDED": "Excluded",
    "SYN-DCIS-REVIEW": "Needs Review",
}


def main():
    patients = json.loads(
        (ROOT / "synthetic patient" / "synthetic_patients_simple.json").read_text(
            encoding="utf-8"
        )
    )
    failures = 0
    print(f"Trial: {TRIAL_ID}", flush=True)
    print("Patient | Expected | Actual | Check", flush=True)
    for patient_id, expected in EXPECTED.items():
        matches = [p for p in patients if p.get("patient_id") == patient_id]
        if len(matches) != 1:
            print(f"{patient_id} | {expected} | missing/duplicate patient | FAIL")
            failures += 1
            continue

        output = run_full_pipeline(matches[0], {"trial_id": TRIAL_ID})
        agent1, agent2 = output["agent1"], output["agent2"]
        results = agent2.get("results", [])
        actual = agent2.get("summary", {}).get("overall", "Unavailable")
        errors = [
            stage.get("message", "Pipeline stage failed")
            for stage in (agent1, agent2)
            if stage.get("status") != "success"
        ]
        errors.extend(
            r.get("reason", "") for r in results
            if "API ERROR" in r.get("reason", "")
            or "LLM not configured" in r.get("reason", "")
        )
        if not results or len(results) != len(agent1.get("rules", [])):
            errors.append("Missing or incomplete rule results")
        passed = actual == expected and not errors
        failures += int(not passed)
        print(
            f"{patient_id} | {expected} | {actual} | {'PASS' if passed else 'FAIL'}",
            flush=True,
        )
        for error in dict.fromkeys(errors):
            print(f"  ERROR: {error}", flush=True)
        if not passed:
            for rule in results:
                if rule["result"] in ("Unknown", "Not Met"):
                    print(
                        f"  {rule['rule_id']}: {rule['result']} - {rule['reason']}",
                        flush=True,
                    )
    print(f"{len(EXPECTED) - failures}/{len(EXPECTED)} cases passed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
