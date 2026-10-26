"""
Runs Agent 2 on ONLY the 10 patient-trial pairs from the ground-truth
evaluation set (evaluation/ground_truth_test_set.csv), and saves the full
PER-RULE output (not just the summary counts) so it can be compared against
evaluation/ground_truth_rule_level_detail.csv.

Why this is a separate script instead of reusing agent2_matcher.py's
__main__ block: that block only saves the summary (met/not_met/unknown
counts) to match_results.csv, not each individual rule's result and reason
-- and for the report's Section 5 tables (accuracy, confusion matrix,
explanation quality, error analysis), we need the per-rule detail. Running
only these 10 pairs (not all 200) keeps this fast and cheap instead of
re-running the whole batch.

Usage: put this file in your agent2_src folder (next to agent2_matcher.py)
and run:
    python3 run_ground_truth_pairs.py

Needs your real .env / ANTHROPIC_API_KEY to be set up exactly like your
normal runs -- this makes real LLM calls (about 190 of them across the 10
pairs), so it will take a few minutes and use a small amount of API credit.
Output: agent2_rule_level_output.csv in your project root -- upload that
file back so the comparison against the ground truth can be done.
"""

import sys, os, json, glob, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent2_matcher as m

# The exact 10 pairs from evaluation/ground_truth_test_set.csv
PAIRS = [
    ("SYN-002", "NCT07062965"),
    ("SYN-004", "NCT07062965"),
    ("SYN-005", "NCT05950945"),
    ("SYN-011", "NCT06625775"),
    ("SYN-013", "NCT06756932"),
    ("SYN-003", "NCT06756932"),
    ("SYN-007", "NCT06120283"),
    ("SYN-016", "NCT07358377"),
    ("SYN-020", "NCT06982521"),
    ("SYN-010", "NCT07368998"),
]


def find_root(marker):
    path = os.getcwd()
    for _ in range(6):
        if os.path.exists(os.path.join(path, marker)):
            return path
        path = os.path.dirname(path)
    return None


def main():
    root = find_root("data/rules/raw") or find_root("evaluation") or os.getcwd()

    patient_matches = glob.glob(os.path.join(root, "**", "synthetic_patients_simple.json"), recursive=True)
    if not patient_matches:
        print("Could not find synthetic_patients_simple.json anywhere under the project folder.")
        return
    with open(patient_matches[0]) as f:
        all_patients = {p["patient_id"]: p for p in json.load(f)}
    print(f"Loaded patients from {patient_matches[0]}")

    trial_dir = os.path.join(root, "data", "rules", "raw")

    rows = []
    for i, (patient_id, trial_id) in enumerate(PAIRS, 1):
        print(f"[{i}/{len(PAIRS)}] {patient_id} x {trial_id} ...", flush=True)
        patient = all_patients[patient_id]
        trial_path = os.path.join(trial_dir, f"{trial_id}.json")
        with open(trial_path) as f:
            trial = json.load(f, strict=False)

        results = m.match_patient_to_trial(patient, trial)
        for r in results:
            rows.append({
                "patient_id": patient_id, "trial_id": trial_id,
                "rule_id": r["rule_id"], "rule_type": r["type"],
                "agent2_result": r["result"], "agent2_reason": r["reason"],
                "logic_group": r.get("logic_group") or "",
            })

    out_path = os.path.join(root, "agent2_rule_level_output.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nDone: {len(rows)} rule-level results across {len(PAIRS)} pairs -> saved to {out_path}")
    print("Upload this file back so the comparison against the ground truth can be run.")


if __name__ == "__main__":
    main()
