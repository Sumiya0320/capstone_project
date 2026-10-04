import streamlit as st

st.title("🎯 Trial Matches")

st.write(
    "Review clinical trials that passed the initial "
    "structured eligibility screening."
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
        "No clinical trials have been searched yet. "
        "Please search for trials first."
    )

    st.stop()


patient = st.session_state["patient"]
trials = st.session_state["processed_trials"]


# =========================================================
# Patient summary
# =========================================================

st.subheader("Patient Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write("**Patient ID**")
    st.write(patient["patient_id"])

with col2:
    st.write("**Condition**")
    st.write(patient["condition"])

with col3:
    st.write("**Age**")
    st.write(patient["age"])

with col4:
    st.write("**Sex**")
    st.write(patient["sex"])


st.divider()


# =========================================================
# Separate trials
# =========================================================

matched_trials = [
    trial
    for trial in trials
    if trial.get("basic_match", False)
]

other_trials = [
    trial
    for trial in trials
    if not trial.get("basic_match", False)
]


# =========================================================
# Metrics
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Trials Retrieved",
        len(trials)
    )

with col2:
    st.metric(
        "Passed Basic Screening",
        len(matched_trials)
    )

with col3:
    st.metric(
        "Filtered Out",
        len(other_trials)
    )


st.divider()


# =========================================================
# Candidate trials
# =========================================================

st.subheader("Candidate Trials")

st.caption(
    "These trials passed the initial age, sex and "
    "location screening. Passing this screening does "
    "not mean the patient is clinically eligible."
)


if len(matched_trials) == 0:

    st.warning(
        "No trials passed all basic screening criteria."
    )

else:

    for index, trial in enumerate(
        matched_trials,
        start=1
    ):

        with st.expander(
            f"{index}. {trial['title']}"
        ):

            st.success(
                "Passed structured pre-screening"
            )

            st.write(
                "**NCT ID:**",
                trial["nct_id"]
            )

            st.write(
                "**Recruitment Status:**",
                trial["status"]
                .replace("_", " ")
                .title()
            )

            if trial["phases"]:

                phases = [
                    phase.replace("_", " ").title()
                    for phase in trial["phases"]
                ]

                st.write(
                    "**Phase:**",
                    ", ".join(phases)
                )

            else:

                st.write(
                    "**Phase:** Not specified"
                )

            st.write(
                "**Age Requirement:**",
                f'{trial["minimum_age"]} – '
                f'{trial["maximum_age"]}'
            )

            st.write(
                "**Sex Requirement:**",
                trial["sex"].title()
            )

            st.markdown(
                "#### Structured Screening"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.success("✓ Age")

            with col2:
                st.success("✓ Sex")

            with col3:
                st.success("✓ Location")

            st.markdown(
                "#### Full Eligibility Criteria"
            )

            st.text(
                trial["eligibility_criteria"]
            )

            st.link_button(
                "View Original Trial",
                "https://clinicaltrials.gov/study/"
                + trial["nct_id"]
            )