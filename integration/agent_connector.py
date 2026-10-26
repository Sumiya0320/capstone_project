# integration/agent_connector.py

import json
from pathlib import Path

from agent2_src.agent2_matcher import (
    match_patient_to_trial,
    summarize
)


# Project root
ROOT = Path(__file__).resolve().parent.parent

# Agent 1's generated rule files
RAW_RULES_DIR = ROOT / "data" / "rules" / "raw"
DRAFT_RULES_DIR = ROOT / "data" / "rules" / "drafts"


def _get_trial_id(trial):
    """
    Get the trial ID regardless of whether the Streamlit
    trial object uses 'trial_id' or 'nct_id'.
    """

    return trial.get("trial_id") or trial.get("nct_id")


def run_agent1(trial):
    """
    Load the structured rules already produced by Agent 1.

    Agent 1 has already converted the raw clinical trial
    eligibility criteria into structured rules and saved them
    under:

        data/rules/raw/<trial_id>.json
    """

    trial_id = _get_trial_id(trial)

    if not trial_id:
        return {
            "status": "error",
            "message": "Trial ID is missing.",
            "trial_id": None,
            "rules": []
        }

    # First look for the newer Agent 1 extraction
    
    rule_file = DRAFT_RULES_DIR / f"{trial_id}.json"

    # Fall back to the older/raw rule files
    if not rule_file.exists():
        rule_file = RAW_RULES_DIR / f"{trial_id}.json"

    if not rule_file.exists():
        return {
            "status": "error",
            "message": (
                f"No Agent 1 rule file found for {trial_id}. "
                f"Checked drafts and raw folders."
            ),
            "trial_id": trial_id,
            "rules": []
        }
    
    try:
        with open(rule_file, "r", encoding="utf-8") as f:
            agent1_output = json.load(f)

        agent1_output["status"] = "success"

        return agent1_output

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "trial_id": trial_id,
            "rules": []
        }


def run_agent2(patient, agent1_output):
    """
    Compare a patient against Agent 1's structured
    eligibility rules using Agent 2.
    """

    if agent1_output.get("status") == "error":
        return {
            "status": "error",
            "message": "Agent 1 output could not be loaded.",
            "results": [],
            "summary": {}
        }

    try:
        results = match_patient_to_trial(
            patient,
            agent1_output
        )

        summary = summarize(results)

        return {
            "status": "success",
            "results": results,
            "summary": summary
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "results": [],
            "summary": {}
        }


def run_full_pipeline(patient, trial):
    """
    Complete eligibility pipeline:

    selected trial
        -> load Agent 1 structured rules
        -> Agent 2 patient/rule matching
        -> eligibility results
        -> eligibility summary
    """

    agent1_output = run_agent1(trial)

    agent2_output = run_agent2(
        patient,
        agent1_output
    )

    return {
        "trial_id": _get_trial_id(trial),
        "agent1": agent1_output,
        "agent2": agent2_output
    }
