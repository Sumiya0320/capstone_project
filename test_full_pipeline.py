import json

from integration.agent_connector import run_full_pipeline


# -------------------------
# Load one synthetic patient
# -------------------------

with open(
    "synthetic patient/synthetic_patients_simple.json",
    "r",
    encoding="utf-8"
) as f:
    patients = json.load(f)

patient = patients[0]


# -------------------------
# Load the corresponding trial
# -------------------------

with open(
    "data/trials/NCT05950945.json",
    "r",
    encoding="utf-8"
) as f:
    trial = json.loads(f.read(), strict=False)
    
# -------------------------
# Run complete pipeline
# -------------------------

result = run_full_pipeline(
    patient=patient,
    trial=trial
)


# -------------------------
# Print results
# -------------------------

print("\n===== PATIENT =====")
print(patient.get("patient_id"))


print("\n===== TRIAL =====")
print(
    trial.get("trial_id")
    or trial.get("nct_id")
)


print("\n===== AGENT 1 =====")
print(
    "Status:",
    result["agent1"].get("status")
)

print(
    "Rules:",
    len(result["agent1"].get("rules", []))
)


print("\n===== AGENT 2 =====")
print(
    "Status:",
    result["agent2"].get("status")
)

print("\nSUMMARY:")
print(
    result["agent2"].get("summary")
)


print("\nFIRST 5 RULE RESULTS:")

for rule in result["agent2"].get("results", [])[:5]:

    print(
        rule["rule_id"],
        "|",
        rule["result"],
        "|",
        rule["description"]
    )