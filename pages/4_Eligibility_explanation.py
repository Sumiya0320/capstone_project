import streamlit as st
from integration.agent_connector import run_full_pipeline


st.title("🧠 Eligibility Explanation")

st.write(
    "Review why a patient may or may not meet the "
    "eligibility requirements for a selected clinical trial."
)

st.info(
    "This tool provides decision support only. "
    "Final eligibility must be determined by the clinical trial team."
)

st.divider()


# =========================================================
# Check required data
# =========================================================

if "patient" not in st.session_state:
    st.warning(
        "No patient profile found. "
        "Please complete the Patient Profile first."
    )
    st.stop()


if "processed_trials" not in st.session_state:
    st.warning(
        "No clinical trials found. "
        "Please search for clinical trials first."
    )
    st.stop()


patient = st.session_state["patient"]
trials = st.session_state["processed_trials"]


# =========================================================
# Only trials that passed structured screening
# =========================================================

candidate_trials = [
    trial
    for trial in trials
    if trial.get("basic_match", False)
]


if not candidate_trials:
    st.warning(
        "No trials passed the initial structured screening."
    )
    st.stop()


# =========================================================
# Select trial
# =========================================================

st.subheader("Select Clinical Trial")

trial_options = {
    f"{trial['nct_id']} — {trial['title']}": trial
    for trial in candidate_trials
}

selected_name = st.selectbox(
    "Clinical Trial",
    list(trial_options.keys())
)

selected_trial = trial_options[selected_name]


st.divider()


# =========================================================
# Patient and trial overview
# =========================================================

left, right = st.columns(2)


with left:

    st.subheader("Patient")

    st.write(
        "**Patient ID:**",
        patient["patient_id"]
    )

    st.write(
        "**Condition:**",
        patient["condition"]
    )

    st.write(
        "**Age:**",
        patient["age"]
    )

    st.write(
        "**Sex:**",
        patient["sex"]
    )

    st.write(
        "**Location:**",
        patient["location"]
    )

    st.write(
        "**Disease Stage:**",
        patient["stage"]
    )

    st.write(
        "**Biomarkers:**",
        patient["biomarkers"]
    )


with right:

    st.subheader("Clinical Trial")

    st.write(
        "**NCT ID:**",
        selected_trial["nct_id"]
    )

    st.write(
        "**Title:**",
        selected_trial["title"]
    )

    st.write(
        "**Status:**",
        selected_trial["status"]
        .replace("_", " ")
        .title()
    )

    st.write(
        "**Age Requirement:**",
        f'{selected_trial["minimum_age"]} – '
        f'{selected_trial["maximum_age"]}'
    )

    st.write(
        "**Sex Requirement:**",
        selected_trial["sex"].title()
    )


st.divider()


# =========================================================
# Structured screening
# =========================================================

st.subheader("Structured Pre-Screening")

col1, col2, col3 = st.columns(3)


with col1:

    if selected_trial.get("age_match"):
        st.success("✓ Age — Met")
    else:
        st.error("✗ Age — Not Met")


with col2:

    if selected_trial.get("sex_match"):
        st.success("✓ Sex — Met")
    else:
        st.error("✗ Sex — Not Met")


with col3:

    if selected_trial.get("location_match"):
        st.success("✓ Location — Met")
    else:
        st.error("✗ Location — Not Met")


st.divider()


# =========================================================
# Full eligibility criteria
# =========================================================

st.subheader("Full Trial Eligibility Criteria")

st.caption(
    "These criteria were retrieved from the "
    "ClinicalTrials.gov study record."
)

st.text(
    selected_trial["eligibility_criteria"]
)


st.divider()


# =========================================================
# AI eligibility section - placeholder
# =========================================================

st.subheader("Detailed Eligibility Assessment")

st.write(
    "The next stage will analyse each inclusion and "
    "exclusion criterion against the patient profile."
)


if st.button(
    "Analyse Eligibility",
    type="primary"
):

    with st.spinner(
        "Running eligibility assessment..."
    ):

        result = run_full_pipeline(
            patient,
            selected_trial
        )

        st.session_state[
            "eligibility_result"
        ] = result


if "eligibility_result" in st.session_state:

    result = st.session_state[
        "eligibility_result"
    ]

    agent1_result = result["agent1"]
    agent2_result = result["agent2"]

    st.markdown("### Agent Status")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Agent 1**")

        if agent1_result["status"] == "not_connected":
            st.warning("Not connected")

        else:
            st.success("Connected")

    with col2:
        st.write("**Agent 2**")

        if agent2_result["status"] == "not_connected":
            st.warning("Not connected")

        else:
            st.success("Connected")


st.divider()


st.link_button(
    "View Original Clinical Trial",
    "https://clinicaltrials.gov/study/"
    + selected_trial["nct_id"]
)