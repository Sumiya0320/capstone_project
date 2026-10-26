# Evaluation and Results

The current deterministic Agent 2 unit-test suite passed (31/31 tests). Unit-test pass rates assess implementation behavior and are not estimates of clinical eligibility accuracy. The repository contains 23 synthetic patients; this evaluation selects 60 patient–rule reference rows and 3 patient–trial verdict rows. Only explicit, independently verified human references with matching input hashes are eligible. Unreviewed, blank and placeholder approvals are excluded.

| Measurement | Eligible sample size | Correct | Result |
|---|---:|---:|---|
| Agent 1 extraction F1 | 0 trials | 0 rules | Not Yet Evaluated |
| Agent 2 rule-level accuracy | 0 rules | 0 | Not Yet Evaluated |
| Patient verdict accuracy | 0 pairs | 0 | Not Yet Evaluated |
| Genuine missing-information Unknown recall | 0 rules | 0 | Not Yet Evaluated |

Agent 1 precision: Not Yet Evaluated; recall: Not Yet Evaluated; missing rules: 0; incorrect/unsupported rules: 0. Zero counts with zero eligible samples do not indicate zero errors. Unknown precision for missing-information detection: Not Yet Evaluated. All-cause Unknown precision: Not Yet Evaluated.

DCIS controlled patient-level smoke validation: Not run (requires paid API calls). This checks three deliberately constructed cases, not independent rule-level accuracy. Live tests require paid API calls. Existing match_results.csv contains aggregate counts only and cannot recover individual decisions or technical-error reasons.

The previously reported 94.1% extraction performance, 67.6% rule-level accuracy, and 97/156 (62.2%) missing-information result cannot currently be verified. No independent estimate is reported until reference review is completed. Extraction precision, recall and F1 must not be compared to an undefined historical “accuracy” as if they were identical.

The selected reference rows contain 0 proposed Unknown labels and 0 explicitly matcher-derived labels. These counts do not establish 97 correct Unknown predictions. No historical rule-level prediction artifact was found in the initial inventory.

## Limitations and required reference work

Independently annotate all atomic inclusion/exclusion criteria from original trial sources, retaining source quotations, logical alternatives, conditions, thresholds and polarity. Confirm complete reference coverage and adjudicate every extracted rule. A source downloaded after extraction must be checked for version differences. Schema validity is not extraction quality.

Independently review the 60 selected rule labels against frozen patient records and criteria, replace circular labels, and document why each Unknown is caused by missing information or clinical ambiguity. Resolve assumptions about treatment-history completeness. Review patient verdicts separately. Export matching uncollapsed rule predictions with error reasons. Technical and missing predictions count as incorrect in the full reference denominator; they never count as successful Unknown predictions. Explain any partial reviewed subset and class imbalance before generalizing.

Explanations remain Not Yet Evaluated. Use the human-review rubric and bind each review to the exact saved prediction hash. No automated explanation score is claimed. Evaluation is incomplete.
