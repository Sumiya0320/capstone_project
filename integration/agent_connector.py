# integration/agent_connector.py


def run_agent1(trial):
    """
    Agent 1 integration point.

    Eventually this function will call Anujin's Agent 1.
    Agent 1 should process the selected clinical trial
    and return structured eligibility criteria.
    """

    # Temporary placeholder
    return {
        "status": "not_connected",
        "trial_id": trial.get("nct_id"),
        "criteria": []
    }


def run_agent2(patient, criteria):
    """
    Agent 2 integration point.

    Eventually this function will call Sumiya's Agent 2.

    Agent 2 should compare the patient information
    against the structured eligibility criteria.
    """

    # Temporary placeholder
    return {
        "status": "not_connected",
        "results": []
    }


def run_full_pipeline(patient, trial):
    """
    Runs the complete eligibility assessment pipeline.

    Trial
      -> Agent 1
      -> structured criteria
      -> Agent 2
      -> eligibility results
    """

    agent1_output = run_agent1(trial)

    criteria = agent1_output.get(
        "criteria",
        []
    )

    agent2_output = run_agent2(
        patient,
        criteria
    )

    return {
        "agent1": agent1_output,
        "agent2": agent2_output
    }