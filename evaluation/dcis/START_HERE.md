# Start here: DCIS review for four students

Open this file first. Scope: **NCT04916808 only**, three existing synthetic DCIS
patients, 20 extracted rules, 60 patient-rule decisions. This is a controlled
capstone case study, not an external clinical validation cohort or reproduction
of historical multi-trial performance.

## Current evidence audit

**No existing reference labels are independently verified.** In the original
`evaluation/labels/`, all 291 extraction judgments, 11 trial-review rows, 210
patient-rule decisions and 10 verdicts are unreviewed. The extraction-reference
CSV is empty; 210 explanation rows have no scores. Of the 210 draft decisions,
27 explicitly came from the matcher and 156 are provisionally Unknown. The
original 10-pair approval fields explicitly describe pre-deadline placeholders.
The word “manual” in a draft's source field does not prove independent review.

The old DCIS smoke test saved only three overall outcomes. Its expected verdicts
were chosen by construction. IDs containing ELIGIBLE, EXCLUDED or REVIEW are
fixture names, not independent labels. All 60 human expected labels in this
pack start **blank**. All 3 human verdicts and all explanation scores are blank.

The official registry record has now been downloaded to
`source/NCT04916808.registry.json`. Readable criteria are in `source/criteria.txt`
and `source/source_clauses.csv`: **7 numbered inclusions and 4 exclusions**.
The record's last update is 2026-04-03. The preparation timestamp, source URL,
hashes and fixed sample are in `input_manifest.json`. `patient_profiles.json`
and `extracted_rules.json` freeze the reviewed inputs.

Still missing: independently adjudicated atomic source references and labels,
extraction-time source/version evidence, reviewed verdicts, and human explanation
scores. Check whether the newly downloaded source matches the source used by
Agent 1; obtain the historical version or disclose version uncertainty if needed.
The separately saved live predictions are model outputs, never ground truth.
No historical individual prediction dataset establishes the claimed 97/156.

## Team assignments: two sessions of about 60–90 minutes

| Students | Independent first pass | Reconciliation and scoring |
|---|---|---|
| 1 and 2 | Each annotate all 11 original clauses before seeing extracted rules | Agree atomic references, assess all 20 extractions; student 3 adjudicates unresolved differences |
| 3 and 4 | Each label the same 60 patient-rule cases before seeing predictions | Agree final labels and 3 verdicts; student 1 adjudicates differences; each score the same 12 explanations |

Replace student numbers with actual names. Do not split the 60 cases into two
nonoverlapping halves: two independent passes expose disagreements. Escalate
unresolved clinical interpretation to your supervisor rather than guessing.

## 1. Agent 1: source first, extraction second

Students 1 and 2 open `source/criteria.txt` and their own
`labels/agent1_source_review_student_1.csv` / `...student_2.csv`. Keep
`extracted_rules.json` and `labels/agent1_matches.csv` closed for this first pass.
For every original clause record atomic requirements, polarity, AND/OR structure,
thresholds and exceptions. Include requirements absent from the extraction.

Reconcile into **`labels/agent1_reference.csv`**, one agreed atomic requirement
per row. Fill `trial_id=NCT04916808`, unique IDs such as `DCIS-REF-001`,
`reference_rule`, exact `source_quote` and the four approval fields below.
The file is deliberately empty: deriving the reference from extracted rules
would make recall circular. Agree atomic granularity before assessing extraction.

Then open **`labels/agent1_matches.csv`**: all 20 extracted rules, declared source
text, fields, operators, applicability and groups. `candidate_source_clause`
is only an exact-text navigation aid. Fill `reference_id` for a semantically
correct match to your independently written reference. Leave it blank for an
incorrect/unsupported rule and explain why in `reference_evidence`. Review every
row. A second extraction matching an already-matched reference counts as an extra
extraction; an unmatched reference is a missing rule. Do not edit application
rules or alter granularity to improve scores.

Specific comparison prompts, **not scored findings**:

* IN-2: single breast, histological confirmation, and permitted LCIS/benign disease.
* IN-3 / rule 03: whether the added applicability condition follows the original
  consent-within-120-days wording or introduces unsupported behavior.
* IN-6 / rules 06–07: female sex and age **greater than 25**, without double counting.
* EX-1 / rules 09–13: OR alternatives; tissue insufficiency versus required-input
  absence; documented false versus unavailable facts.
* EX-2 / rules 14–18: justified separate atomic findings versus overlapping or
  duplicate invasive-disease statements.
* EX-4 / rule 20: prior breast cancer versus current DCIS.

Complete **`labels/agent1_trials.csv`** last: check source path/hash and version,
set `reference_complete=yes`, then approve only after checking source coverage.

For a completed human adjudication, the four approval fields are:

| Field | Fill with |
|---|---|
| review_status | verified |
| reviewed_by | Actual reviewer names; include adjudicator where needed |
| independent | yes, only after genuine independent review |
| reference_evidence | Source clause IDs, specific patient fields if relevant, and reasoning |

## 2. Agent 2: blind labels, then comparison

Students 3 and 4 read `patient_profiles.json`, original criteria, and their own
**`labels/agent2_blind_student_3.csv` / `...student_4.csv`**. Each has 60 rows,
with rule text and frozen hashes but no predicted or suggested expected label.
Keep `coordinator_only/` closed until both independent passes are saved. This
folder separation is a workflow convention, not an access-control mechanism.
Blinding is partial: fixture IDs hint at intended overall outcomes. Disclose
that limitation and justify each rule label from evidence, never from its ID.

Fill `expected_result`, specific `reference_evidence`, and the four approval
fields. Consider the whole patient record, not only the rule's mapped field.

| Label | Patient eligibility meaning |
|---|---|
| Met | Inclusion satisfied, or exclusion positively shown absent |
| Not Met | Inclusion violated, or exclusion positively present |
| Unknown | Available evidence cannot establish whether the condition holds |
| Not Applicable | A documented applicability condition demonstrably does not apply |

Unknown also requires `unknown_cause=missing_information` or `clinical_ambiguity`.
API failures, missing keys for API configuration, and unsupported operators are
technical failures, never human Unknown references. Patient `false` is a
documented negative; `null` or absent data is unavailable evidence.

Reconcile into **`labels/agent2_reference.csv`**. Copy agreed labels, causes and
evidence, name both reviewers, and approve. Record disagreements, adjudicator
name and resolution in `adjudication_notes`. Keep original blind decisions
unchanged so disagreements remain auditable. No script assigns or approves labels.

Review **`labels/patient_reference.csv`** separately, applying original trial
logic to independently reviewed decisions without calling the system summarizer.
Any failed inclusion/triggered exclusion yields Excluded; otherwise unresolved
applicable criteria yield Needs Review; otherwise Likely Eligible. Resolve OR
groups with the correct polarity. Fill the three verdicts, rationale and approval.

Only then open **`coordinator_only/agent2_review_table.csv`**, which shows all
patients, rules, human expected labels, actual predictions and actual reasons.
After editing labels, refresh this derived comparison without API calls:

```powershell
./.venv/Scripts/python.exe -B evaluation/dcis_review.py refresh
```

Do not change a reference merely to agree with the prediction. Document any
genuine annotation correction as an amendment after unblinding.

## 3. Independently verify missing-information cases

The primary prespecified candidate is **SYN-DCIS-REVIEW / NCT04916808_08**:
`able_to_provide_informed_consent=null`. Verify that the source requires consent
ability and no other patient field establishes it. This is a candidate for
Unknown, **not a preapproved expected label**.

All other 59 decisions also need review: a populated field may fail to cover a
compound criterion. `coordinator_only/missing_information_review.csv` includes
the prespecified candidate and every actual/reference Unknown. Check age,
tumour size, margin status and `palpability=false` are documented, not missing.
Do not confuse missing documentation with a confirmed clinical exclusion.
Record exactly which needed facts are unavailable for each reference Unknown.

If only one genuine missing-information reference remains, report recall with
denominator **one** and its limitation. This cannot support broad performance
claims. Do not add patients or trials merely to improve the denominator.

## 4. Explanation quality: 12 cases, 24 independent ratings

After references are frozen, students 3 and 4 open
**`coordinator_only/explanation_sample.csv`** and **`labels/explanation_review.csv`**.
The fixed sample was selected before collection: 4 cases per patient covering
age, undocumented consent, conditional surgery, tissue, required inputs, invasive
disease and prior history. Keep these cases even if predictions surprise you.
It is purposive coverage, not a random or statistically representative sample;
Not Applicable coverage is not guaranteed.

Fill your own review-slot rows: actual name, `prediction_sha256` copied from the
sample table, five scores and evidence-based notes. Blank means unreviewed.
Higher always means better, including the unsupported-assumptions dimension.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Correctness | Wrong factual/clinical reasoning | Partly correct; material omission | Correct against independent references |
| Decision consistency | Contradicts predicted label/polarity | Unclear connection | Clearly supports predicted label/polarity |
| Grounding | Invented/contradicted evidence | Vague/incomplete evidence | Specific supporting patient fields and source criteria |
| Missing information | Guesses missing facts or confuses technical errors with data gaps | Recognises uncertainty without needed facts | Identifies unavailable facts, or correctly establishes none are needed |
| Unsupported assumptions | Material unsupported assumption | Minor unsupported inference | No unsupported assumptions |

A wrong decision may still have internally consistent wording: score dimensions
separately. Do not replace a technical-error explanation with an imagined
successful explanation. Keep original scores; discuss differences in notes.
The evaluator reports per-dimension means/distributions and exact inter-reviewer
agreement, using two distinct named reviewers per case. It creates no composite.

## 5. Final command, after human review (offline)

Checklist: complete atomic source reference; all 20 extraction judgments and
trial completeness approved; two blind and final labels for all 60 decisions;
all 3 verdicts approved; 24 explanation ratings and prediction hashes filled.
Keep dated copies of labels before unblinding and after adjudication.

```powershell
./.venv/Scripts/python.exe -B evaluation/dcis_review.py evaluate
```

Open **`evaluation/dcis/results/evaluation_summary.json`**, `evaluation_report.md`
and `explanation_evaluation.json`. Expected scope: 1 reviewed trial, 60 raw rule
decisions, 3 verdicts, independently verified missing-information cases, and
12 paired explanation cases. Missing reviews stay Not Yet Evaluated or stop
finalisation. Existing multi-trial results remain separate. Do not describe this
small case study as reproducing 94.1%, 67.6% or 97/156.

## Rebuilding or collecting

`prepare` creates missing templates without overwriting human work and rejects
changed input hashes. `refresh` rebuilds only derived coordinator tables.

```powershell
./.venv/Scripts/python.exe -B evaluation/dcis_review.py prepare
# PAID; only if the frozen prediction export is absent:
./.venv/Scripts/python.exe -B evaluation/dcis_review.py collect
```

`collect` calls only the three DCIS pairs and refuses to overwrite predictions.
Archive the pack before a later rerun. Do not use the older unscoped
`run_evaluation.py --collect`, whose default is the original ten-pair dataset.
