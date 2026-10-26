import streamlit as st
import hashlib
import json


def assessment_key(patient, trial_id):
    fingerprint = hashlib.sha256(
        json.dumps(patient, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"eligibility_{trial_id}_{fingerprint}"

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


if "screened_trials" not in st.session_state:
    st.warning(
        "No clinical trials found. "
        "Please search for clinical trials first."
    )
    st.stop()


patient = st.session_state["patient"]
candidate_trials = st.session_state["screened_trials"]


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
        patient.get("patient_id", "Not specified")
    )

    st.write(
        "**Condition:**",
        patient.get("condition", "Not specified")
    )

    st.write(
        "**Age:**",
        patient.get("age", "Not specified")
    )

    st.write(
        "**Sex:**",
        patient.get("sex", "Not specified")
    )

    st.write(
        "**Location:**",
        patient.get("location", "Not specified")
    )

    st.write(
        "**Disease Stage:**",
        patient.get("stage", "Not specified")
    )

    st.write(
        "**Biomarkers:**",
        patient.get("biomarkers", "Not specified")
    )


with right:
    st.subheader("Clinical Trial")

    st.write(
        "**NCT ID:**",
        selected_trial.get("nct_id", "Unknown")
    )

    st.write(
        "**Title:**",
        selected_trial.get("title", "No title available")
    )

    status = selected_trial.get("status", "Unknown")

    st.write(
        "**Status:**",
        status.replace("_", " ").title()
    )

    st.write(
        "**Age Requirement:**",
        f"{selected_trial.get('minimum_age', 'Not specified')} – "
        f"{selected_trial.get('maximum_age', 'Not specified')}"
    )

    st.write(
        "**Sex Requirement:**",
        selected_trial.get("sex", "Not specified").title()
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
    selected_trial.get(
        "eligibility_criteria",
        "Eligibility criteria not available."
    )
)


st.divider()


# =========================================================
# Full eligibility assessment
# =========================================================

st.subheader("Detailed Eligibility Assessment")

st.write(
    "The next stage analyses inclusion and exclusion "
    "criteria against the patient profile."
)

result_key = assessment_key(patient, selected_trial["nct_id"])


if result_key in st.session_state:
    st.info("A saved assessment is available for this patient and trial. No new API request is needed.")
    if st.button("Clear saved assessment"):
        del st.session_state[result_key]
        st.rerun()

if st.button(
    "Analyse Eligibility",
    type="primary",
    disabled=result_key in st.session_state,
):

    with st.spinner(
        "Running eligibility assessment..."
    ):

        try:
            result = run_full_pipeline(
                patient,
                selected_trial
            )

            st.session_state[
                result_key
            ] = result

        except Exception as error:
            st.error(
                f"Unable to run eligibility assessment: {error}"
            )


# =========================================================
# Display eligibility result
# =========================================================

if result_key in st.session_state:

    result = st.session_state[result_key]

    agent1_result = result.get(
        "agent1",
        {}
    )

    agent2_result = result.get(
        "agent2",
        {}
    )

    st.divider()

    # =====================================================
    # Agent statuses
    # =====================================================
    st.markdown("### Agent Status")
    for name, output in (("Agent 1", agent1_result), ("Agent 2", agent2_result)):
        status = output.get("status", "unknown")
        if status == "success":
            st.success(f"{name}: Success")
        else:
            st.error(f"{name}: {status} — {output.get('message', 'See raw output for details')}")

    st.divider()
    st.markdown("### Eligibility Summary")
    summary = agent2_result.get("summary", {})
    criteria_results = agent2_result.get("results", [])
    api_failures = [
        item for item in criteria_results
        if (
            "LLM call FAILED" in item.get("reason", "")
            or "API ERROR" in item.get("reason", "")
            or "completion token limit" in item.get("reason", "")
        )
    ]

    if agent1_result.get("status") != "success" or agent2_result.get("status") != "success":
        st.error("The assessment did not complete successfully.")
    elif not criteria_results:
        st.warning("No eligibility rules were evaluated. No eligibility conclusion can be drawn.")
    else:
        overall = summary.get("overall", "Unavailable")
        if api_failures:
            st.warning(
                f"{len(api_failures)} rule(s) encountered API errors. "
                "The preliminary outcome is incomplete and needs review."
            )
        if overall == "Excluded":
            st.error("Preliminary outcome: Excluded (one or more rules not met)")
        elif overall == "Needs Review":
            st.warning("Preliminary outcome: Needs Review")
        elif overall == "Likely Eligible":
            st.success("Preliminary outcome: Likely Eligible — requires clinical verification")
        else:
            st.info(f"Preliminary outcome: {overall}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Met", summary.get("met", 0))
    col2.metric("Not Met", summary.get("not_met", 0))
    col3.metric("Unknown", summary.get("unknown", 0))
    col4.metric("Not Applicable", summary.get("not_applicable", 0))

    st.divider()
    st.markdown("### Detailed Criteria Assessment")
    if not criteria_results:
        st.info("No detailed eligibility results available.")
    else:
        for item in criteria_results:
            outcome = item.get("result", "Unknown")
            reason = item.get("reason", "")
            with st.container(border=True):
                st.write(f"**{item.get('type', 'Unknown').title()} — {item.get('rule_id', 'Rule')}**")
                st.write(item.get("description", "Unnamed criterion"))
                if (
                    "LLM call FAILED" in reason
                    or "API ERROR" in reason
                    or "completion token limit" in reason
                ):
                    st.error("AI processing failed — manual review required")
                elif outcome == "Met":
                    st.success("Met")
                elif outcome == "Not Met":
                    st.error("Not Met")
                elif outcome == "Not Applicable":
                    st.info("Not Applicable")
                else:
                    st.warning("Unknown")
                if reason:
                    st.caption(reason)

    # =====================================================
    # Raw development output
    # =====================================================

    with st.expander(
        "View Raw Agent Output"
    ):
        st.json(result)


st.divider()


# =========================================================
# Original trial
# =========================================================

if selected_trial.get("nct_id"):

    st.link_button(
        "View Original Clinical Trial",
        "https://clinicaltrials.gov/study/"
        + selected_trial["nct_id"]
    )