"""Patient Profile page for synthetic-data clinical trial eligibility research."""
import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_PATH = ROOT / "synthetic patient" / "synthetic_patients_simple.json"


def display_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def optional_number(text, kind=float):
    text = text.strip()
    if not text:
        return None
    try:
        value = kind(text)
    except ValueError:
        raise ValueError(f"Enter a valid number or leave blank: {text!r}")
    if value < 0:
        raise ValueError("Numerical clinical values cannot be negative in this form.")
    return value


def clear_old_assessments():
    # A result from a different patient must never be displayed as current.
    for key in list(st.session_state.keys()):
        if key.startswith("eligibility_"):
            del st.session_state[key]


st.title("👤 Patient Profile")
st.write("Enter clinical information or load a synthetic research patient. Leave unavailable clinical values blank; they will be treated as unknown.")
st.info("Research demonstration only. Use synthetic records, not identifiable patient information. Trial staff determine clinical eligibility.")

# Optional synthetic dataset for reproducible demonstrations.
if SYNTHETIC_PATH.is_file():
    try:
        records = json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8"))
        if isinstance(records, dict):
            records = records.get("patients", [])
        if not isinstance(records, list):
            raise ValueError("Expected a list of synthetic patients")
        records = [r for r in records if isinstance(r, dict)]
        with st.expander("Load an existing synthetic patient", expanded=False):
            if records:
                chosen = st.selectbox(
                    "Synthetic patient",
                    range(len(records)),
                    format_func=lambda i: str(records[i].get("patient_id", f"Patient {i+1}")),
                )
                if st.button("Load synthetic patient"):
                    st.session_state["patient"] = records[chosen].copy()
                    clear_old_assessments()
                    st.rerun()
            else:
                st.warning("The synthetic patient file contains no records.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Could not load synthetic patients: {exc}")

existing = st.session_state.get("patient", {})
if not isinstance(existing, dict):
    existing = {}

st.divider()
st.subheader("Basic Information")
with st.form("patient_profile_form"):
    left, right = st.columns(2)
    with left:
        patient_id = st.text_input("Patient ID", value=display_text(existing.get("patient_id")))
        age = st.number_input("Age", min_value=0, max_value=120, step=1,
                              value=int(existing.get("age") or 0))
    with right:
        sex_options = ["Select", "Female", "Male", "Other / Not specified"]
        prior_sex = existing.get("sex", "Select")
        sex = st.selectbox("Sex", sex_options,
                           index=sex_options.index(prior_sex) if prior_sex in sex_options else 0)
        location = st.text_input("Location", value=display_text(existing.get("location")),
                                 placeholder="e.g. Sydney, NSW")

    st.subheader("Diagnosis and Disease Characteristics")
    condition = st.text_input("Primary condition / diagnosis",
                              value=display_text(existing.get("condition") or existing.get("diagnosis")))
    stage = st.text_input("Disease stage", value=display_text(existing.get("cancer_stage") or existing.get("stage")),
                          placeholder="e.g. Stage IV")
    col_a, col_b = st.columns(2)
    with col_a:
        ecog_options = ["Unknown", "0", "1", "2", "3", "4"]
        current_ecog = str(existing.get("ecog")) if existing.get("ecog") is not None else "Unknown"
        ecog = st.selectbox("ECOG performance status", ecog_options,
                            index=ecog_options.index(current_ecog) if current_ecog in ecog_options else 0)
        her2 = st.text_input("HER2 status", value=display_text(existing.get("her2_status")),
                             placeholder="e.g. Positive, Negative, Unknown")
        pik3ca = st.text_input("PIK3CA mutation status",
                               value=display_text(existing.get("pik3ca_status") or
                                                  (existing.get("biomarkers", {}).get("PIK3CA_status")
                                                   if isinstance(existing.get("biomarkers"), dict) else None)))
    with col_b:
        hr = st.text_input("Hormone receptor status (HR / ER / PR)",
                           value=display_text(existing.get("hormone_receptor_status")))
        menopause = st.text_input("Menopausal status", value=display_text(existing.get("menopausal_status")))
        lvef = st.text_input("LVEF (%)", value=display_text(existing.get("lvef_percent")),
                              placeholder="Blank if not known")

    st.subheader("Treatment and Clinical Evidence")
    previous_treatment = st.text_area("Previous treatments",
                                      value=display_text(existing.get("prior_treatments", existing.get("previous_treatment"))))
    current_treatment = st.text_area("Current treatment", value=display_text(existing.get("current_treatment")))
    medications = st.text_area("Current medications", value=display_text(existing.get("medications")))
    prior_lines = st.text_input("Prior metastatic therapy lines (number)",
                                value=display_text(existing.get("prior_metastatic_lines")))
    life_weeks = st.text_input("Life expectancy (weeks)",
                               value=display_text(existing.get("life_expectancy_weeks")))
    brain_metastases = st.selectbox("Brain metastases documented?", ["Unknown", "Yes", "No"],
                                    index=(1 if existing.get("brain_metastases") is True else
                                           2 if existing.get("brain_metastases") is False else 0))
    progression_evidence = st.text_area("Documented recurrence/progression evidence",
                                       value=display_text(existing.get("progression_evidence")))
    pathology = st.text_area("Pathology/histology confirmation",
                             value=display_text(existing.get("pathology_confirmation")))
    measurability = st.text_area("Measurable disease / RECIST evidence",
                                value=display_text(existing.get("measurable_disease_evidence")))
    st.subheader("Other Clinical Information")
    biomarkers_text = st.text_area("Additional biomarkers (free text or JSON)",
                                   value=display_text(existing.get("biomarkers")),
                                   help="A JSON object preserves structured biomarker fields from synthetic records.")
    medical_conditions = st.text_area("Other medical conditions",
                                      value=display_text(existing.get("medical_conditions")))
    consent = st.selectbox("Informed consent documented?", ["Unknown", "Yes", "No"],
                           index=(1 if existing.get("informed_consent") is True else
                                  2 if existing.get("informed_consent") is False else 0))
    save = st.form_submit_button("Save Patient Profile", type="primary")

if save:
    if not patient_id.strip():
        st.error("Please enter a patient ID.")
    elif not condition.strip():
        st.error("Please enter the primary condition.")
    elif sex == "Select":
        st.error("Please select the patient's sex.")
    else:
        try:
            lvef_number = optional_number(lvef, float)
            prior_lines_number = optional_number(prior_lines, int)
            life_weeks_number = optional_number(life_weeks, float)
            if lvef_number is not None and lvef_number > 100:
                raise ValueError("LVEF must be between 0 and 100.")
            biomarker_value = biomarkers_text.strip()
            if biomarker_value.startswith("{"):
                biomarker_value = json.loads(biomarker_value)
                if not isinstance(biomarker_value, dict):
                    raise ValueError("Biomarker JSON must be an object.")
            patient = existing.copy()  # Preserve additional keys supplied by synthetic data.
            patient.update({
                "patient_id": patient_id.strip(), "age": int(age), "sex": sex,
                "location": location.strip(), "condition": condition.strip(),
                "diagnosis": condition.strip(), "stage": stage.strip() or None,
                "cancer_stage": stage.strip() or None,
                "ecog": None if ecog == "Unknown" else int(ecog),
                "her2_status": her2.strip() or None,
                "hormone_receptor_status": hr.strip() or None,
                "menopausal_status": menopause.strip() or None,
                "pik3ca_status": pik3ca.strip() or None,
                "lvef_percent": lvef_number,
                "prior_metastatic_lines": prior_lines_number,
                "life_expectancy_weeks": life_weeks_number,
                "brain_metastases": None if brain_metastases == "Unknown" else brain_metastases == "Yes",
                "previous_treatment": previous_treatment.strip() or None,
                "prior_treatments": previous_treatment.strip() or None,
                "current_treatment": current_treatment.strip() or None,
                "medications": medications.strip() or None,
                "biomarkers": biomarker_value or None,
                "medical_conditions": medical_conditions.strip() or None,
                "progression_evidence": progression_evidence.strip() or None,
                "pathology_confirmation": pathology.strip() or None,
                "measurable_disease_evidence": measurability.strip() or None,
                "informed_consent": None if consent == "Unknown" else consent == "Yes",
            })
            # Preserve structured PIK3CA value under common nested key too.
            if isinstance(patient["biomarkers"], dict) and pik3ca.strip():
                patient["biomarkers"]["PIK3CA_status"] = pik3ca.strip()
            st.session_state["patient"] = patient
            clear_old_assessments()
            st.success("Patient profile saved. Previous eligibility assessments were cleared because patient data may have changed.")
            st.json(patient)
        except (ValueError, json.JSONDecodeError) as exc:
            st.error(str(exc))
