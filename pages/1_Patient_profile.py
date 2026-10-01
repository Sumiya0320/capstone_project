import streamlit as st

st.title("👤 Patient Profile")

st.write(
    "Enter the patient's information below. "
    "This information will later be used to identify potentially relevant clinical trials."
)

st.divider()

# Basic information
st.subheader("Basic Information")

col1, col2 = st.columns(2)

with col1:
    patient_id = st.text_input("Patient ID")
    age = st.number_input("Age", min_value=0, max_value=120, step=1)

with col2:
    sex = st.selectbox(
        "Sex",
        ["Select", "Female", "Male", "Other / Not specified"]
    )

    location = st.text_input(
        "Location",
        placeholder="e.g. Sydney, NSW"
    )

# Medical information
st.subheader("Medical Information")

condition = st.text_input(
    "Primary Condition / Diagnosis",
    placeholder="e.g. Breast Cancer"
)

stage = st.text_input(
    "Disease Stage",
    placeholder="e.g. Stage II"
)

current_treatment = st.text_area(
    "Current Treatment",
    placeholder="Enter current treatment information"
)

previous_treatment = st.text_area(
    "Previous Treatments",
    placeholder="Enter previous treatments"
)

medications = st.text_area(
    "Current Medications",
    placeholder="Enter medications"
)

# Additional clinical information
st.subheader("Additional Clinical Information")

biomarkers = st.text_area(
    "Relevant Biomarkers",
    placeholder="e.g. HER2 negative, ER positive"
)

medical_conditions = st.text_area(
    "Other Medical Conditions"
)

st.divider()

# Save button
if st.button("Save Patient Profile", type="primary"):

    st.session_state["patient"] = {
        "patient_id": patient_id,
        "age": age,
        "sex": sex,
        "location": location,
        "condition": condition,
        "stage": stage,
        "current_treatment": current_treatment,
        "previous_treatment": previous_treatment,
        "medications": medications,
        "biomarkers": biomarkers,
        "medical_conditions": medical_conditions
    }

    st.success("Patient profile saved successfully!")