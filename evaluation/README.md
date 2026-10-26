# Reproducible evaluation

For the manageable four-student **NCT04916808-only** review, open
[`dcis/START_HERE.md`](dcis/START_HERE.md) first. Independent labels start blank;
actual predictions are separate from blind review sheets. The official registry
source is now saved under `dcis/source/`; retrieval is not human annotation.

Run from the repository root in the VS Code PowerShell terminal:

```powershell
./.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py' -v
./.venv/Scripts/python.exe -B evaluation/run_evaluation.py
```

The default run makes **no API calls**. It runs the existing 31 matcher unit
tests, creates review templates only if absent, and evaluates saved predictions
against independently verified references. Existing application files and draft
labels are untouched. Outputs go to `evaluation/results/`. Undefined metrics
are JSON `null` / blank CSV cells, displayed as **Not Yet Evaluated**.
Ratios in JSON/CSV are 0–1; the report displays percentages. The metric unit
tests use arithmetic fixtures and must not be cited as empirical study results.

## Existing evidence

`ground_truth_rule_level_detail.csv` has 210 draft decisions for 10 pairs.
`ground_truth_test_set.csv` has 10 aggregate verdicts. Its approval fields
explicitly describe pre-deadline placeholders. The accompanying methodology
says some labels came from the matcher itself. Neither file is independently
verified ground truth. `match_results.csv` has aggregate counts, not individual
predictions/explanations, so it cannot establish rule-level accuracy or Unknown
recall. The DCIS script has three deliberately constructed patient-level cases;
it is an integration smoke test, not an independent clinical validation set.

## Review workflow

Templates in `labels/` are intentionally **unreviewed**. Do not simply approve
model-derived labels. A reviewer must reassign/check each label independently
using the patient profile and original trial criteria, without seeing predictions.
Record `review_status=verified`, a named `reviewed_by`, `independent=yes`, and
specific `reference_evidence`. Preserve patient/rule hashes; changed inputs need
fresh independent review, not just replacement hashes. Resolve disagreements
with a second reviewer and document adjudication in the evidence field.

* Agent 1: independently enumerate atomic original criteria in
  `agent1_reference.csv` with stable reference IDs and verbatim source quotes.
  Include rules omitted by Agent 1. Do not build the reference by copying the
  extraction. In `agent1_trials.csv`, identify the dated local original source,
  its SHA256 and complete-reference approval. For NCT04916808 use the saved
  official record under `dcis/source/` and check its version against the
  extraction-time source, which is not available locally.
  In `agent1_matches.csv`, adjudicate **every** extracted rule. Map a semantically
  correct extraction to one reference ID; leave the ID blank for incorrect or
  unsupported rules, explaining why in `reference_evidence`. Check polarity,
  threshold, applicability and OR/AND grouping. Split/merge rules into a consistent
  atomic granularity before review. Duplicate extractions count as false positives.
  An unmatched reference is a false negative. Only fully adjudicated trials enter
  micro-averaged precision, recall and F1. Schema checks do not count as accuracy.
* Agent 2: independently review/relabel each raw, **uncollapsed** rule in
  `agent2_reference.csv`. Use exactly `Met`, `Not Met`, `Unknown`, or
  `Not Applicable`. Unknown references require `unknown_cause=missing_information`
  or `clinical_ambiguity`; technical failures are never reference Unknowns.
  Cite unavailable facts for missing-information cases. Verify treatment-history
  completeness rather than assuming absence from a list proves no prior therapy.
* Verdicts: review `patient_reference.csv` independently. Do not derive reference
  verdicts by calling the matcher or its summarizer. Apply documented trial logic.
  Patient-level agreement is reported separately and cannot establish rule accuracy.

Evaluate saved full pipeline predictions:

```powershell
./.venv/Scripts/python.exe -B evaluation/run_evaluation.py --predictions evaluation/results/pipeline_predictions.json
```

For **paid OpenAI API calls**, with the configured key and network access:

```powershell
# Three DCIS patients, approximately 42 LLM rule checks, plus possible retries:
./.venv/Scripts/python.exe -B evaluation/run_evaluation.py --run-dcis
# All 10 draft patient–trial pairs, up to 210 rule checks, plus retries:
./.venv/Scripts/python.exe -B evaluation/run_evaluation.py --collect
```

`--collect` calls the real `run_full_pipeline()` without changing its behavior.
It exports full outputs, timestamps, model and patient hashes to
`results/pipeline_predictions.json`. It never creates reference labels. Do not
overwrite a publication's prediction artifact; archive each run and its input
manifest. For external exports, use the same JSON envelope: `records` list, each
with `patient_id`, `patient_sha256` (SHA256 of `json.dumps(patient, sort_keys=True)`),
`trial_id`, `agent1`, and `agent2` from `run_full_pipeline()`. Missing/stale
patient or rule provenance is treated as failure. Verify export provenance;
hashes identify input versions but do not prove independent annotation.

All approved current references remain in accuracy/recall denominators, including
technical failures and absent predictions. They are counted as incorrect, with a
separate `Technical/Missing` confusion column. Technical Unknowns never contribute
true positives or successful-prediction counts. Reasons currently emitted by the
matcher identify missing keys, API errors, unsupported operators and comparison
errors. Error detection is conservative and string-based; review reasons when
the matcher changes. Missing-information recall uses only independently labelled
missing-information Unknown cases. Its precision uses all nontechnical predicted
Unknowns in the evaluated cohort as denominator, so clinical ambiguity is not a
successful detection of genuinely missing information. All-cause Unknown precision
is also reported separately.

## Explanation rubric (human review; no invented scores)

Freeze predictions, then fill `labels/explanation_review.csv`. Record reviewer,
notes, and SHA256 of the exact prediction JSON. Include patient/rule IDs to join
the actual explanation and reference evidence. Blank scores mean not evaluated;
they must not be converted to zero. Score each dimension 0–2:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Correctness | Incorrect clinical/rule reasoning | Partly correct, material omission | Correct relative to independently reviewed evidence |
| Decision consistency | Contradicts predicted class/polarity | Ambiguous link | Clearly supports predicted class and polarity |
| Grounding | Invented or contradicted evidence | Incomplete/vague evidence | Explicitly supported by patient facts and trial wording |
| Missing information | Guesses missing facts or confuses technical error with missing data | Recognizes uncertainty without identifying needed facts | Identifies relevant unavailable facts; or correctly establishes none are needed |
| Unsupported assumptions | Material unsupported clinical assumption | Minor unsupported inference | No unsupported assumptions |

Higher is better for every dimension, including unsupported assumptions. Review
the same frozen sample independently with two reviewers, adjudicate differences,
and report per-dimension distributions, sample sizes and inter-reviewer agreement
before any composite score. This framework supplies the template and rubric;
it deliberately reports explanation quality as Not Yet Evaluated until that
review is performed. It does not automatically aggregate human scores.

## Reporting

Required CSVs, class metrics, confusion matrix, separate verdict results, JSON
manifest, unit-test transcript and a short academic `evaluation_report.md` are
generated under `results/`. Empty evaluation CSVs contain headers only; there
are no eligible independent reference cases yet. The historical 94.1%, 67.6%
and 97/156 figures remain unverified, not contradicted by an absence of labels.
The historical extraction “accuracy” also needs an explicit metric definition
and original cohort/prediction artifacts before comparison with extraction F1.
