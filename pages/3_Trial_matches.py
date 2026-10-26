import streamlit as st
import hashlib
import json

from pathlib import Path

from integration.agent_connector import run_full_pipeline

ROOT = Path(__file__).resolve().parent.parent
RAW_RULES_DIR = ROOT / "data" / "rules" / "raw"
DRAFT_RULES_DIR = ROOT / "data" / "rules" / "drafts"


def find_rule_file(trial_id):
    draft_file = DRAFT_RULES_DIR / f"{trial_id}.json"
    raw_file = RAW_RULES_DIR / f"{trial_id}.json"

    if draft_file.is_file():
        return draft_file

    if raw_file.is_file():
        return raw_file

    return None

def assessment_key(patient, trial_id):
    fingerprint = hashlib.sha256(
        json.dumps(patient, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"eligibility_{trial_id}_{fingerprint}"





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


if "screened_trials" not in st.session_state:
    st.warning(
        "No screened clinical trials found. "
        "Please search for trials first."
    )
    st.stop()


patient = st.session_state["patient"]
trials = st.session_state["screened_trials"]
# Search page preserves all retrieved trials, including pre-screening failures.
all_trials = st.session_state.get("candidate_trials", trials)
screened_out_trials = [
    trial for trial in all_trials if not trial.get("basic_match", False)
]



# =========================================================
# Patient summary
# =========================================================

st.subheader("Patient Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write("**Patient ID**")
    st.write(patient.get("patient_id", "Not specified"))

with col2:
    st.write("**Condition**")
    st.write(patient.get("condition", "Not specified"))

with col3:
    st.write("**Age**")
    st.write(patient.get("age", "Not specified"))

with col4:
    st.write("**Sex**")
    st.write(patient.get("sex", "Not specified"))


st.divider()


# =========================================================
# Metrics
# =========================================================

ready_trials = [
    trial for trial in trials
    if find_rule_file(trial.get("nct_id")) is not None
]

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Passed Pre-Screening", len(trials))

with col2:
    st.metric("Ready for Full Assessment", len(ready_trials))

with col3:
    st.metric(
        "Requires Criteria Extraction",
        len(trials) - len(ready_trials)
    )


# =========================================================
# Candidate trials
# =========================================================

st.subheader("Candidate Trials")

st.caption(
    "These trials passed the initial age, sex and location "
    "screening. Passing this screening does not mean the "
    "patient is clinically eligible."
)


if len(trials) == 0:

    st.warning(
        "No trials passed all basic screening criteria."
    )

else:

    for index, trial in enumerate(
        trials,
        start=1
    ):

        with st.expander(
            f"{index}. {trial.get('title', 'Untitled Trial')}"
        ):

            st.success(
                "✓ Passed structured pre-screening"
            )

            st.write(
                "**NCT ID:**",
                trial.get("nct_id", "Unknown")
            )

            status = trial.get(
                "status",
                "Unknown"
            )

            st.write(
                "**Recruitment Status:**",
                status.replace("_", " ").title()
            )

            # =================================================
            # Phase
            # =================================================

            phases = trial.get(
                "phases",
                []
            )

            if phases:

                formatted_phases = [
                    phase.replace("_", " ").title()
                    for phase in phases
                ]

                st.write(
                    "**Phase:**",
                    ", ".join(formatted_phases)
                )

            else:

                st.write(
                    "**Phase:** Not specified"
                )


            # =================================================
            # Basic eligibility information
            # =================================================

            st.write(
                "**Age Requirement:**",
                f"{trial.get('minimum_age', 'Not specified')} – "
                f"{trial.get('maximum_age', 'Not specified')}"
            )

            st.write(
                "**Sex Requirement:**",
                trial.get(
                    "sex",
                    "Not specified"
                ).title()
            )


            # =================================================
            # Structured screening result
            # =================================================

            st.markdown(
                "#### Structured Screening"
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                if trial.get(
                    "age_match",
                    False
                ):
                    st.success("✓ Age")
                else:
                    st.error("✗ Age")

            with col2:

                if trial.get(
                    "sex_match",
                    False
                ):
                    st.success("✓ Sex")
                else:
                    st.error("✗ Sex")

            with col3:

                if trial.get(
                    "location_match",
                    False
                ):
                    st.success("✓ Location")
                else:
                    st.error("✗ Location")


            # =================================================
            # Full eligibility criteria
            # =================================================

            st.markdown(
                "#### Full Eligibility Criteria"
            )

            eligibility_criteria = trial.get(
                "eligibility_criteria",
                "Eligibility criteria not available."
            )

            st.text(
                eligibility_criteria
            )


            # =================================================
            # Full agent pipeline
            # =================================================

            st.markdown(
                "#### Full Eligibility Assessment"
            )

            st.caption(
                "This step will use the eligibility agents "
                "to analyse the patient's detailed clinical "
                "information against the trial criteria."
            )

            trial_id = trial.get(
                "nct_id",
                f"trial_{index}"
            )
            rule_file = find_rule_file(trial_id)
            rules_available = rule_file is not None
            if rules_available:
                st.success(
                    f"Agent 1 criteria available — ready for assessment "
                    f"({rule_file.parent.name})"
                )
            else:
                st.warning(
                    "Agent 1 has not extracted criteria for this trial yet."
                )

            result_key = assessment_key(patient, trial_id)

            if result_key in st.session_state:
                if st.button("Clear saved assessment", key=f"clear_{trial_id}"):
                    del st.session_state[result_key]
                    st.rerun()

            if st.button(
                "Run Full Eligibility Check",
                key=f"check_{trial_id}",
                disabled=not rules_available
            ):
                with st.spinner(
                    "Running eligibility assessment..."
                ):

                    try:

                        result = run_full_pipeline(
                            patient,
                            trial
                        )

                        st.session_state[
                            result_key
                        ] = result

                    except Exception as error:

                        st.error(
                            "Unable to run the eligibility "
                            f"assessment: {error}"
                        )


            # =================================================
            # Display agent result
            # =================================================

            if result_key in st.session_state:

                result = st.session_state[
                    result_key
                ]

                st.markdown(
                    "##### Eligibility Result"
                )

                agent1_result = result.get(
                    "agent1",
                    {}
                )

                agent2_result = result.get(
                    "agent2",
                    {}
                )


                # ---------------------------------------------
                # Agent 1 result
                # ---------------------------------------------

                st.write(
                    "**Agent 1 Status:**",
                    agent1_result.get(
                        "status",
                        "Unknown"
                    )
                )


                # ---------------------------------------------
                # Agent 2 result
                # ---------------------------------------------

                st.write(
                    "**Agent 2 Status:**",
                    agent2_result.get(
                        "status",
                        "Unknown"
                    )
                )


                # ---------------------------------------------
                # Eligibility summary
                # ---------------------------------------------
                if agent1_result.get("status") != "success" or agent2_result.get("status") != "success":
                    st.error("Eligibility assessment failed; check agent messages in the raw output.")
                else:
                    summary = agent2_result.get("summary", {})
                    rule_results = agent2_result.get("results", [])
                    api_failures = [
                        r for r in rule_results
                        if (
                            "LLM call FAILED" in r.get("reason", "")
                            or "API ERROR" in r.get("reason", "")
                            or "completion token limit" in r.get("reason", "")
                        )
                    ]
                    if not rule_results:
                        st.warning("No rules were evaluated; no eligibility conclusion can be drawn.")
                    else:
                        st.write("**Preliminary outcome:**", summary.get("overall", "Unavailable"))
                        st.write(
                            f"Met: {summary.get('met', 0)} | "
                            f"Not Met: {summary.get('not_met', 0)} | "
                            f"Unknown: {summary.get('unknown', 0)} | "
                            f"Not Applicable: {summary.get('not_applicable', 0)}"
                        )
                        if api_failures:
                            st.warning(f"{len(api_failures)} rule(s) failed API processing and need a rerun or manual review.")
                        st.caption("Screening support only; trial staff determine final eligibility.")

                # ---------------------------------------------
                # Temporary raw result
                # ---------------------------------------------

                with st.expander(
                    "View Raw Agent Output"
                ):

                    st.json(
                        result
                    )


            # =================================================
            # ClinicalTrials.gov link
            # =================================================

            st.divider()

            if trial.get("nct_id"):

                st.link_button(
                    "View Original Trial",
                    "https://clinicaltrials.gov/study/"
                    + trial["nct_id"]
                )

# =========================================================
# Trials excluded by basic pre-screening
# =========================================================
st.divider()
st.subheader(f"Screened-Out Trials ({len(screened_out_trials)})")
st.caption(
    "These trials were not sent to the full eligibility pipeline because "
    "at least one preliminary age, sex, or location check did not pass. "
    "This is not a final clinical eligibility determination."
)

if not screened_out_trials:
    st.info("No retrieved trials were screened out by the basic checks.")
else:
    for trial in screened_out_trials:
        trial_id = trial.get("nct_id", "Unknown")
        title = trial.get("title", "Untitled Trial")
        with st.expander(f"{title} ({trial_id})"):
            st.warning("Did not pass preliminary screening")
            st.write("**Recruitment status:**", str(trial.get("status", "Unknown")).replace("_", " ").title())
            for field, label in [
                ("age_match", "Age"),
                ("sex_match", "Sex"),
                ("location_match", "Location"),
            ]:
                if trial.get(field, False):
                    st.success(f"✓ {label}: passed")
                else:
                    st.error(f"✗ {label}: did not pass")
            reasons = trial.get("match_reasons", [])
            st.markdown("**Recorded screening reasons**")
            if reasons:
                for reason in reasons:
                    st.write("•", reason)
            else:
                st.info("No detailed rejection reasons were recorded. Review the search-page screening logic.")
            st.write(
                "**Trial age range:**",
                f"{trial.get('minimum_age', 'Not specified')} – "
                f"{trial.get('maximum_age', 'Not specified')}",
            )
            st.write("**Trial sex requirement:**", trial.get("sex", "Not specified"))
            if trial.get("nct_id"):
                st.link_button(
                    "View Original Trial",
                    "https://clinicaltrials.gov/study/" + trial["nct_id"],
                )
