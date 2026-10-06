"""
Synthetic patient data generator (SIMPLIFIED version) for breast-cancer
clinical trial eligibility screening.

Trimmed down from the original 20-field version to just the criteria that
matter most for breast-cancer trial eligibility: diagnosis, stage, the
ER/PR/HER2 biomarkers that define which trial a patient even belongs to,
ECOG performance status, prior treatment history, and 2 key lab values
(ANC and platelet count -- the two most commonly checked across trials).

Field names match Agent 1's PATIENT_FIELDS list exactly (age, sex, ecog,
lvef_percent, life_expectancy_weeks, prior_metastatic_lines,
hormone_receptor_status, her2_status, brain_metastases) so that Agent 2's
python-checkable rules can actually find the value on the patient record
instead of falling back to "Unknown" because of a naming mismatch.
ecog_performance_status was renamed to ecog; her2_status and
hormone_receptor_status are added as flat top-level fields (her2_status
mirrors biomarkers.HER2_status, hormone_receptor_status is derived: HR+ if
either ER or PR is Positive); lvef_percent, life_expectancy_weeks,
prior_metastatic_lines and brain_metastases are new synthetic fields that
didn't exist in the patient record at all before.

Dropped vs. the original richer version: the full 7-value lab panel (kept
only 2), washout period, metastasis site, RECIST measurable-disease flag,
pregnancy flag, prior-other-malignancy flag, comorbidities, and
consent-ability flag. These are real concepts but added complexity beyond
what a first version needs -- add them back later only if your actual trial
criteria call for them.

Deliberately missing information: real clinical records are sometimes
incomplete, and Agent 2 (the matcher) is built to handle that gracefully by
returning "Unknown" for any rule whose required field is missing. To make
sure that path is actually tested (not just theoretically supported), a
handful of patients below have specific fields deliberately set to null --
see MISSING_INFO_PLAN.

Output: synthetic_patients_simple.json (list of patient objects) in this folder.
Deterministic: re-running with the same PATIENT_SEED reproduces the same data
(the missing-info plan is applied afterward and is also fixed/deterministic).
"""

import json
import random

PATIENT_SEED = 42
random.seed(PATIENT_SEED)

N_PATIENTS = 20

DIAGNOSES = [
    "Invasive ductal carcinoma",
    "Invasive lobular carcinoma",
    "Ductal carcinoma in situ (DCIS)",
    "Triple-negative breast carcinoma",
    "Inflammatory breast carcinoma",
]

STAGES = ["0", "I", "II", "III", "IV"]
STAGE_WEIGHTS = [0.05, 0.25, 0.30, 0.20, 0.20]

ECOG_WEIGHTS = {0: 0.35, 1: 0.35, 2: 0.15, 3: 0.10, 4: 0.05}

PRIOR_TREATMENT_OPTIONS = [
    "surgery", "chemotherapy", "radiation therapy",
    "hormone therapy", "targeted therapy (anti-HER2)", "immunotherapy",
]


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def random_key_labs(impaired: bool):
    """Just the 2 most commonly-checked lab values across breast-cancer trials."""
    if impaired:
        return {
            "absolute_neutrophil_count_per_uL": round(random.uniform(800, 1400), 0),  # normal >=1500
            "platelet_count_per_uL": round(random.uniform(60000, 95000), 0),          # normal >=100000
        }
    return {
        "absolute_neutrophil_count_per_uL": round(random.uniform(1600, 6500), 0),
        "platelet_count_per_uL": round(random.uniform(150000, 380000), 0),
    }


def make_patient(idx: int):
    patient_id = f"SYN-{idx:03d}"

    age = random.randint(28, 82)
    sex = "Female" if random.random() > 0.03 else "Male"
    if sex == "Female":
        menopausal_status = "Postmenopausal" if age >= 52 else random.choice(
            ["Premenopausal", "Perimenopausal"]
        )
    else:
        menopausal_status = "N/A"

    diagnosis = random.choice(DIAGNOSES)
    stage = weighted_choice(STAGES, STAGE_WEIGHTS)

    if diagnosis == "Triple-negative breast carcinoma":
        er_status = pr_status = "Negative"
        her2_status = "Negative"
    else:
        er_status = random.choice(["Positive", "Negative"])
        pr_status = random.choice(["Positive", "Negative"])
        her2_status = random.choices(
            ["Positive", "Negative", "Equivocal"], weights=[0.2, 0.7, 0.1]
        )[0]

    ecog = random.choices(list(ECOG_WEIGHTS.keys()), weights=list(ECOG_WEIGHTS.values()))[0]

    n_prior = random.randint(0, 3)
    prior_treatments = random.sample(PRIOR_TREATMENT_OPTIONS, k=n_prior) if n_prior else ["none"]

    impaired_organ_function = random.random() < 0.25
    key_labs = random_key_labs(impaired_organ_function)

    # Standard clinical convention: hormone-receptor-positive if EITHER ER or
    # PR is Positive.
    hormone_receptor_status = "Positive" if "Positive" in (er_status, pr_status) else "Negative"

    # LVEF (heart pump function): normal is roughly 55-70%; many trials
    # exclude patients below 50%, so give ~15% of patients a low value to
    # actually exercise that threshold.
    lvef_percent = round(random.uniform(35, 49), 0) if random.random() < 0.15 else round(random.uniform(55, 70), 0)

    # Estimated life expectancy: most trials require a minimum (commonly
    # >=12 weeks); a handful of patients fall under that on purpose.
    life_expectancy_weeks = random.randint(4, 12) if random.random() < 0.10 else random.randint(13, 260)

    # Number of prior lines of therapy given specifically for metastatic
    # (stage IV) disease -- independent of the general prior_treatments list.
    prior_metastatic_lines = random.choices([0, 1, 2, 3, 4], weights=[0.35, 0.3, 0.2, 0.1, 0.05])[0]

    brain_metastases = random.random() < 0.12

    return {
        "patient_id": patient_id,
        "age": age,
        "sex": sex,
        "menopausal_status": menopausal_status,
        "diagnosis": diagnosis,
        "cancer_stage": stage,
        "biomarkers": {
            "ER_status": er_status,
            "PR_status": pr_status,
            "HER2_status": her2_status,
        },
        "ecog": ecog,
        "her2_status": her2_status,                        # flat alias of biomarkers.HER2_status
        "hormone_receptor_status": hormone_receptor_status,
        "lvef_percent": lvef_percent,
        "life_expectancy_weeks": life_expectancy_weeks,
        "prior_metastatic_lines": prior_metastatic_lines,
        "brain_metastases": brain_metastases,
        "prior_treatments": prior_treatments,
        "key_lab_values": key_labs,
    }


patients = [make_patient(i) for i in range(1, N_PATIENTS + 1)]


# --- Deliberately introduce missing information --------------------------
# Fixed (not random) so it's reproducible and easy to reason about. Covers
# a mix of field types so each of Agent 2's checkers gets a real "Unknown"
# test case: a numeric field, a categorical field, a list-type field used
# by both categorical_contains and text_interpretation rules, and an
# entire nested lab-values block missing.
MISSING_INFO_PLAN = {
    "SYN-005": ["ecog"],                               # numeric check -> Unknown
    "SYN-011": ["her2_status", "biomarkers.HER2_status"],  # categorical check -> Unknown
    "SYN-016": ["prior_treatments"],                   # categorical_contains / text_interpretation -> Unknown
    "SYN-020": ["key_lab_values"],                     # whole lab panel missing -> Unknown
}


def apply_missing_info(patient_list, plan):
    by_id = {p["patient_id"]: p for p in patient_list}
    for patient_id, dotted_fields in plan.items():
        patient = by_id.get(patient_id)
        if patient is None:
            continue
        for dotted_field in dotted_fields:
            parts = dotted_field.split(".")
            target = patient
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = None
    return patient_list


patients = apply_missing_info(patients, MISSING_INFO_PLAN)

out_path = "synthetic_patients_simple.json"
with open(out_path, "w") as f:
    json.dump(patients, f, indent=2)

print(f"Generated {len(patients)} synthetic patients (simplified) -> {out_path}")
print(f"Deliberately missing fields applied to: {', '.join(MISSING_INFO_PLAN.keys())}")
