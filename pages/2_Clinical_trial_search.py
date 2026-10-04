import streamlit as st
import requests


st.title("🔎 Clinical Trial Search")

st.write(
    "Search ClinicalTrials.gov for clinical trials relevant "
    "to the patient's condition."
)

st.divider()


# =========================================================
# ClinicalTrials.gov API
# =========================================================

def search_trials(condition, australia_only=False):

    url = "https://clinicaltrials.gov/api/v2/studies"

    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING|NOT_YET_RECRUITING|ACTIVE_NOT_RECRUITING",
        "pageSize": 50,
        "format": "json"
    }

    if australia_only:
        params["query.locn"] = "Australia"

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    return response.json().get("studies", [])

def age_to_years(age_text):

    if not age_text or age_text == "Not specified":
        return None

    try:
        number = float(age_text.split()[0])

        if "Year" in age_text:
            return number

        elif "Month" in age_text:
            return number / 12

        elif "Week" in age_text:
            return number / 52

        elif "Day" in age_text:
            return number / 365

    except (ValueError, IndexError):
        return None

    return None

def check_basic_eligibility(patient, trial):

    reasons = []

    # -------------------------
    # AGE CHECK
    # -------------------------

    patient_age = patient.get("age")

    minimum_age = age_to_years(
        trial["minimum_age"]
    )

    maximum_age = age_to_years(
        trial["maximum_age"]
    )

    age_match = True

    if minimum_age is not None:
        if patient_age < minimum_age:
            age_match = False
            reasons.append(
                f"Patient is younger than minimum age "
                f"({trial['minimum_age']})."
            )

    if maximum_age is not None:
        if patient_age > maximum_age:
            age_match = False
            reasons.append(
                f"Patient is older than maximum age "
                f"({trial['maximum_age']})."
            )

    # -------------------------
    # SEX CHECK
    # -------------------------

    patient_sex = patient.get(
        "sex",
        ""
    ).upper()

    trial_sex = trial.get(
        "sex",
        ""
    ).upper()

    sex_match = (
        trial_sex in ["ALL", "NOT SPECIFIED", ""]
        or patient_sex == trial_sex
    )

    if not sex_match:
        reasons.append(
            f"Trial requires sex: {trial['sex']}."
        )

    # -------------------------
    # LOCATION CHECK
    # -------------------------

    patient_location = patient.get(
        "location",
        ""
    ).lower()

    location_match = False

    matching_locations = []

    for location in trial["australian_locations"]:

        city = location.get(
            "city",
            ""
        ).lower()

        state = location.get(
            "state",
            ""
        ).lower()

        # Sydney patient
        if "sydney" in patient_location:

            if "sydney" in city:
                location_match = True
                matching_locations.append(location)

            elif state in [
                "new south wales",
                "nsw"
            ]:
                location_match = True
                matching_locations.append(location)

        # NSW patient
        elif (
            "nsw" in patient_location
            or "new south wales" in patient_location
        ):

            if state in [
                "new south wales",
                "nsw"
            ]:
                location_match = True
                matching_locations.append(location)

        # Other Australian location
        elif (
            city
            and city in patient_location
        ):

            location_match = True
            matching_locations.append(location)

    if not location_match:
        reasons.append(
            "No nearby matching trial location found."
        )

    # -------------------------
    # FINAL BASIC RESULT
    # -------------------------

    basic_match = (
        age_match
        and sex_match
        and location_match
    )

    return {
        "basic_match": basic_match,
        "age_match": age_match,
        "sex_match": sex_match,
        "location_match": location_match,
        "matching_locations": matching_locations,
        "reasons": reasons
    }


# =========================================================
# Extract useful trial information
# =========================================================

def extract_trial_info(trial):

    protocol = trial.get("protocolSection", {})

    identification = protocol.get(
        "identificationModule", {}
    )

    status_module = protocol.get(
        "statusModule", {}
    )

    design_module = protocol.get(
        "designModule", {}
    )

    eligibility_module = protocol.get(
        "eligibilityModule", {}
    )

    contacts_module = protocol.get(
        "contactsLocationsModule", {}
    )

    conditions_module = protocol.get(
        "conditionsModule", {}
    )

    # Basic information
    nct_id = identification.get(
        "nctId",
        "Unknown"
    )

    title = identification.get(
        "briefTitle",
        "No title available"
    )

    status = status_module.get(
        "overallStatus",
        "Unknown"
    )

    conditions = conditions_module.get(
        "conditions",
        []
    )

    # Trial phases
    phases = design_module.get(
        "phases",
        []
    )

    # Eligibility information
    minimum_age = eligibility_module.get(
        "minimumAge",
        "Not specified"
    )

    maximum_age = eligibility_module.get(
        "maximumAge",
        "Not specified"
    )

    sex = eligibility_module.get(
        "sex",
        "Not specified"
    )

    eligibility_criteria = eligibility_module.get(
        "eligibilityCriteria",
        "Eligibility criteria not available."
    )

    # Locations
    locations = contacts_module.get(
        "locations",
        []
    )

    australian_locations = []

    for location in locations:

        country = location.get("country", "")

        if country.lower() == "australia":

            city = location.get(
                "city",
                "Unknown city"
            )

            state = location.get(
                "state",
                ""
            )

            facility = location.get(
                "facility",
                ""
            )

            australian_locations.append({
                "facility": facility,
                "city": city,
                "state": state
            })

    return {
        "nct_id": nct_id,
        "title": title,
        "status": status,
        "conditions": conditions,
        "phases": phases,
        "minimum_age": minimum_age,
        "maximum_age": maximum_age,
        "sex": sex,
        "eligibility_criteria": eligibility_criteria,
        "australian_locations": australian_locations
    }


# =========================================================
# Patient profile
# =========================================================

if "patient" not in st.session_state:

    st.warning(
        "No patient profile has been saved yet. "
        "Please complete the Patient Profile first."
    )

else:

    patient = st.session_state["patient"]

    st.subheader("Current Patient")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Patient ID**")
        st.write(patient["patient_id"])

    with col2:
        st.write("**Condition**")
        st.write(patient["condition"])

    with col3:
        st.write("**Location**")
        st.write(patient["location"])

    st.divider()

    # =====================================================
    # Search controls
    # =====================================================

    st.subheader("Search Trials")

    condition = st.text_input(
        "Condition",
        value=patient["condition"]
    )

    australia_only = st.checkbox(
        "Show Australian trials only",
        value=True
    )

    if st.button(
        "Search Clinical Trials",
        type="primary"
    ):

        if not condition:

            st.warning(
                "Please enter a medical condition."
            )

        else:

            with st.spinner(
                "Searching ClinicalTrials.gov..."
            ):

                try:

                    raw_trials = search_trials(
                        condition,
                        australia_only
                    )

                    processed_trials = []

                    for trial in raw_trials:

                        trial_info = extract_trial_info(
                            trial
                        )
                        basic_result = check_basic_eligibility(
                            patient,
                            trial_info
                        )

                        trial_info["basic_match"] = basic_result[
                            "basic_match"
                        ]

                        trial_info["age_match"] = basic_result[
                            "age_match"
                        ]

                        trial_info["sex_match"] = basic_result[
                            "sex_match"
                        ]

                        trial_info["location_match"] = basic_result[
                            "location_match"
                        ]

                        trial_info["match_reasons"] = basic_result[
                            "reasons"
                        ]

                        if australia_only:

                            if len(
                                trial_info[
                                    "australian_locations"
                                ]
                            ) > 0:

                                processed_trials.append(
                                    trial_info
                                )

                        else:

                            processed_trials.append(
                                trial_info
                            )

                    st.session_state[
                        "processed_trials"
                    ] = processed_trials

                except requests.RequestException as error:

                    st.error(
                        f"Unable to retrieve trials: {error}"
                    )


# =========================================================
# Display trials
# =========================================================

if "processed_trials" in st.session_state:

    trials = st.session_state[
        "processed_trials"
    ]

    st.divider()

    st.subheader(
        f"Relevant Trials ({len(trials)})"
    )

    if len(trials) == 0:

        st.warning(
            "No matching Australian trials were found "
            "in the retrieved results. Try disabling "
            "'Show Australian trials only'."
        )

    else:

        for trial in trials:

            with st.expander(
                trial["title"]
            ):
                if trial["basic_match"]:

                    st.success(
                        "✓ Passed basic eligibility screening"
                    )

                else:

                    st.warning(
                        "⚠ Did not pass all basic screening criteria"
                    )
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if trial["age_match"]:
                            st.success("✓ Age")
                        else:
                            st.error("✗ Age")

                    with col2:
                        if trial["sex_match"]:
                            st.success("✓ Sex")
                        else:
                            st.error("✗ Sex")

                    with col3:
                        if trial["location_match"]:
                            st.success("✓ Location")
                        else:
                            st.error("✗ Location")

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

                # Phase
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

                # Conditions
                st.write(
                    "**Conditions:**",
                    ", ".join(
                        trial["conditions"]
                    )
                )

                # Age
                st.write(
                    "**Age Range:**",
                    f'{trial["minimum_age"]} – '
                    f'{trial["maximum_age"]}'
                )

                # Sex
                st.write(
                    "**Sex:**",
                    trial["sex"].title()
                )

                # Australian locations
                st.write(
                    "**Australian Locations:**"
                )

                if trial[
                    "australian_locations"
                ]:

                    for location in trial[
                        "australian_locations"
                    ]:

                        location_text = (
                            f'{location["facility"]} — '
                            f'{location["city"]}'
                        )

                        if location["state"]:

                            location_text += (
                                f', {location["state"]}'
                            )

                        st.write(
                            "• " + location_text
                        )

                else:

                    st.write(
                        "No Australian locations listed."
                    )

                # Eligibility
                st.markdown(
                    "### Eligibility Criteria"
                )

                st.text(
                    trial[
                        "eligibility_criteria"
                    ]
                )

                # Original study
                st.link_button(
                    "View Full Trial",
                    "https://clinicaltrials.gov/study/"
                    + trial["nct_id"]
                )   