# Explainable Two-Agent AI System for Clinical Trial Eligibility Screening

## Overview

Clinical trials require participants to meet specific inclusion and exclusion
criteria. Manually comparing patient information against these criteria can be
time-consuming and may result in important information being overlooked.

This capstone project develops a small, explainable AI prototype that assists
with clinical trial eligibility screening.

The system uses two AI agents:

1. **Criteria Reader** – converts clinical trial eligibility text into a
   structured checklist of rules.
2. **Matcher & Explainer** – compares a patient profile against each rule and
   returns **Met**, **Not Met**, or **Unknown**, together with an explanation.

The system is designed as a research and learning prototype. It does not make
final medical or clinical decisions.

---

## Project Objectives

The project aims to:

- Convert clinical trial eligibility text into structured rules.
- Compare synthetic patient profiles against each eligibility rule.
- Explain why each criterion is classified as Met, Not Met, or Unknown.
- Mark missing patient information as Unknown instead of guessing.
- Present the results through a simple and understandable web interface.

---

## System Workflow

The system follows the workflow:

Trial Eligibility Text  
↓  
**Agent 1 – Criteria Reader**  
↓  
Structured Rule Checklist  
↓  
**Agent 2 – Matcher & Explainer** ← Synthetic Patient Profile  
↓  
**Met / Not Met / Unknown + Explanation**

---

## Agent 1 – Criteria Reader

Agent 1 reads the eligibility criteria of a clinical trial and converts the
unstructured text into structured JSON rules.

For example:

**Original criterion:**

> Participants must be at least 18 years old.

**Structured rule:**

```json
{
  "criterion": "age",
  "operator": ">=",
  "value": 18,
  "type": "inclusion"
}
