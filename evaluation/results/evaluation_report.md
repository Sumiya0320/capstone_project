# Evaluation and Results

The current deterministic Agent 2 unit-test suite passed (31/31 tests). Unit-test pass rates assess implementation behavior and are not estimates of clinical eligibility accuracy. The repository contains 23 synthetic patients, 210 draft patient–rule labels and 10 draft patient–trial verdicts. The draft labels include matcher-derived decisions and explicit placeholder review approvals; these were excluded from independent evaluation.

| Measurement | Eligible sample size | Correct | Result |
|---|---:|---:|---|
| Agent 1 extraction F1 | 0 trials | 0 rules | Not Yet Evaluated |
| Agent 2 rule-level accuracy | 0 rules | 0 | Not Yet Evaluated |
| Patient verdict accuracy | 0 pairs | 0 | Not Yet Evaluated |
| Genuine missing-information Unknown recall | 0 rules | 0 | Not Yet Evaluated |

Agent 1 precision: Not Yet Evaluated; recall: Not Yet Evaluated; missing rules: 0; incorrect/unsupported rules: 0. Zero counts with zero eligible samples do not indicate zero errors. Unknown precision for missing-information detection: Not Yet Evaluated. All-cause Unknown precision: Not Yet Evaluated.

DCIS controlled patient-level smoke validation: Passed. This checks three deliberately constructed cases, not independent rule-level accuracy. Live tests require paid API calls. Existing match_results.csv contains aggregate counts only and cannot recover individual decisions or technical-error reasons.

The previously reported 94.1% extraction performance, 67.6% rule-level accuracy, and 97/156 (62.2%) missing-information result cannot currently be verified. No independent estimate is reported until reference review is completed. Extraction precision, recall and F1 must not be compared to an undefined historical “accuracy” as if they were identical.

The draft contains 156 Unknown labels, which explains a possible source of the historical denominator 156, but does not establish 97 correct Unknown predictions. There are 27 explicitly matcher-derived draft labels. No historical rule-level prediction artifact was found in the initial inventory.

## Limitations and required reference work

Independently annotate all atomic inclusion/exclusion criteria from original trial sources, retaining source quotations, logical alternatives, conditions, thresholds and polarity. Confirm complete reference coverage and adjudicate every extracted rule. NCT04916808 currently has extracted rules but no original trial file in data/trials; obtain a dated original source before evaluating its extraction. Schema validity is not extraction quality.

Independently review the 210 draft rule labels against frozen patient records and criteria, replace circular labels, and document why each Unknown is caused by missing information or clinical ambiguity. Resolve assumptions about treatment-history completeness. Review patient verdicts separately. Export matching uncollapsed rule predictions with error reasons. Technical and missing predictions count as incorrect in the full reference denominator; they never count as successful Unknown predictions. Explain any partial reviewed subset and class imbalance before generalizing.

Explanations remain Not Yet Evaluated. Use the human-review rubric and bind each review to the exact saved prediction hash. No automated explanation score is claimed. Evaluation is incomplete.
