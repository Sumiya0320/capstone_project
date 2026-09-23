# Explainable Two-Agent AI System for Clinical Trial Eligibility Screening

## Overview

Clinical trials require participants to meet specific inclusion and exclusion criteria. Manually comparing patient information against these criteria can be time-consuming and may result in important information being overlooked.

This capstone project develops a small, explainable AI prototype that assists with clinical trial eligibility screening.

The system uses two AI agents:

1. **Criteria Reader** – converts clinical trial eligibility text into a structured checklist of rules.
2. **Matcher & Explainer** – compares a patient profile against each rule and returns **Met**, **Not Met**, or **Unknown**, together with an explanation.

The system is designed as a research and learning prototype. It does not make final medical or clinical decisions.

## Project Objectives

- Convert clinical trial eligibility text into structured rules.
- Compare synthetic patient profiles against each eligibility rule.
- Explain why each criterion is classified as Met, Not Met, or Unknown.
- Mark missing patient information as Unknown instead of guessing.
- Present the results through a simple and understandable web interface.

## System Workflow

```text
Trial Eligibility Text
        |
        v
Agent 1 - Criteria Reader
        |
        v
Structured Rule Checklist
        |
        v
Agent 2 - Matcher & Explainer <--- Synthetic Patient Profile
        |
        v
Met / Not Met / Unknown + Explanation
```

## Agent 1 - Criteria Reader

Agent 1 reads the eligibility criteria of a clinical trial and converts the unstructured text into structured JSON rules.

For example:

**Original criterion:**

> Participants must be at least 18 years old.

**Example structured rule:**

```json
{
  "criterion": "age",
  "operator": ">=",
  "value": 18,
  "type": "inclusion"
}
```

The generated rules are manually reviewed by the team before being used by Agent 2.

## Agent 2 - Matcher & Explainer

Agent 2 receives the structured eligibility rules from Agent 1 and a synthetic patient profile.

It evaluates the patient against each criterion and returns:

- **Met** – the patient satisfies the criterion.
- **Not Met** – the patient does not satisfy the criterion.
- **Unknown** – the required patient information is unavailable.

Each result includes a short explanation. Simple numeric comparisons, such as age requirements, are handled using standard Python logic, while the LLM handles rules requiring interpretation.

## Dataset

The prototype uses:

- Approximately **10 breast-cancer clinical trials**
- Public trial eligibility criteria from **ClinicalTrials.gov**
- Approximately **20 synthetic patient profiles**
- JSON files for storing trials, patients, rules, and results

No real patient records are used.

## Evaluation

The system will be evaluated using approximately **10 manually labelled patient-trial pairs**, representing around **100 individual eligibility-rule decisions**.

Evaluation focuses on:

- **Agent 1 correctness** – percentage of rules extracted correctly.
- **Agent 2 accuracy** – percentage of rule decisions matching the team's labels.
- **Unknown detection** – how often missing information is correctly marked Unknown rather than guessed.
- **Explanation quality** – whether each explanation is correct and supports the decision.

## Technology Stack

- Python
- LLM API (e.g. GPT or Claude)
- Streamlit
- Pandas
- JSON
- ClinicalTrials.gov
- Git and GitHub

## Proposed Repository Structure

```text
clinical-trial-eligibility/
│
├── data/
│   ├── trials/                 # ~10 breast cancer trials
│   ├── patients/               # ~20 synthetic patient profiles
│   └── labelled_test_set/      # Manually labelled evaluation cases
│
├── src/
│   ├── agent1/
│   │   └── criteria_reader.py
│   ├── agent2/
│   │   └── matcher_explainer.py
│   └── utils/
│
├── results/                    # Agent outputs and evaluation results
├── tests/                      # Tests for system components
│
├── app.py                      # Streamlit application
├── requirements.txt            # Python dependencies
├── .env.example                # Example API configuration
├── .gitignore
└── README.md
```

The repository structure may change as development progresses.

## Team

### Anujin Bat-Erdene
**Primary Role:** Agent 1

Responsibilities:
- Trial collection
- Trial preparation
- Agent 1 validation

### Sumiyabazar Batbold
**Primary Role:** Agent 2

Responsibilities:
- Synthetic patient data
- Deterministic checking logic
- Agent 2 testing

### Duurenjargal Batchuluun
**Primary Role:** Interface & Evaluation

Responsibilities:
- Streamlit interface
- Test-set preparation
- System integration
- Evaluation

All team members contribute to creating and reviewing synthetic patient profiles, manually labelling the evaluation set, integration testing, debugging, GitHub version control, documentation, the final report, presentation slides, and the final demonstration.

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd <repository-name>
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

After installing the dependencies and configuring the required API key:

```bash
streamlit run app.py
```

## Project Timeline

| Phase | Dates | Main Goal |
|---|---|---|
| Setup & Data | 21–27 Sep | Prepare trials, synthetic patients and repository |
| Agent 1 | 28 Sep–4 Oct | Build and validate Criteria Reader |
| Agent 2 & Interface | 5–11 Oct | Build Matcher & Explainer and Streamlit interface |
| Test & Finish | 12–15 Oct | Evaluation, debugging, report and demonstration |

## Scope

### In Scope

- Approximately 10 breast-cancer trials
- Approximately 20 synthetic patients
- Eligibility text to structured rule checklist
- Met / Not Met / Unknown classification
- Explanation for each rule
- Simple Streamlit interface
- Small manually labelled evaluation set

### Out of Scope

- Real patient records or hospital system integration
- Live searching of the whole trial registry
- Trial ranking or treatment recommendations
- Additional verification agents
- Production-quality deployment
- User accounts
- Large benchmark datasets or advanced experiments

## Privacy and Safety

Only synthetic patient data and publicly available clinical trial information are used. No real patient health information should be stored in this repository.

API keys and credentials must not be committed to GitHub.

## Disclaimer

**This project is an academic research prototype and is not a medical tool.**

The system does not provide medical advice, treatment recommendations, or definitive clinical trial eligibility decisions. All system results require human review, and final eligibility decisions must be made by qualified healthcare or clinical research professionals.

## Project Status

**Under Development**

Capstone Project - September to October 2026
