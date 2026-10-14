# Ground-truth evaluation test set (DRAFT -- needs team review)

Built for the "Evaluation and test-set preparation" Trello card. This is a
first-pass draft: **it needs you and your teammates to review it before you
save it as final** (that's the "Have other members review labels" checklist
item -- the `reviewed_by` / `reviewer_agrees` / `review_notes` columns in
`ground_truth_test_set.csv` are intentionally left blank for that).

## What's in here

- **ground_truth_test_set.csv** -- one row per patient-trial pair, with the
  expected `met` / `not_met` / `unknown` / `not_applicable` counts and the
  expected overall verdict (same shape as `match_results.csv`, so you can
  diff them directly). This is the file to compare Agent 2's real output
  against.
- **ground_truth_rule_level_detail.csv** -- the full rule-by-rule reasoning
  behind every number in the summary file (210 individual judgments across
  the 10 pairs). Use this when a summary row looks wrong and you need to see
  *why* a particular rule was labeled the way it was.

## The 10 pairs chosen, and why

Picked to cover the real failure modes you've already seen in your own
200-combination run, not just easy cases:

| Patient | Trial | What it tests |
|---|---|---|
| SYN-002 | NCT07062965 | Baseline case, small (12-rule) trial |
| SYN-004 | NCT07062965 | Same trial, different patient -- shows the verdict actually changes with patient data |
| SYN-005 | NCT05950945 | **Missing ECOG field** (your deliberately-null test patient) -- also happens to be the exact trial you investigated for "time-since-treatment" earlier |
| SYN-011 | NCT06625775 | **Missing HER2 status** (your deliberately-null test patient) |
| SYN-013 | NCT06756932 | Patient *has* brain metastases -- exclusion-rule test |
| SYN-003 | NCT06756932 | Same trial, no brain metastases -- direct contrast with SYN-013 |
| SYN-007 | NCT06120283 | Very poor ECOG (4) -- clean performance-status exclusion |
| SYN-016 | NCT07358377 | **Missing prior_treatments** (your deliberately-null test patient) |
| SYN-020 | NCT06982521 | Trial has python-checked fields (`fasting_plasma_glucose_mg_dL`, `hba1c_percent`) that **don't exist anywhere in your patient schema** -- a real "domain mismatch" trial |
| SYN-010 | NCT07368998 | Wrong HER2 subtype (trial wants HER2-negative, patient is HER2-positive) |

All 4 of your deliberately-missing-field synthetic patients (SYN-005,
SYN-011, SYN-016, SYN-020 also covers a missing-field case by domain
mismatch) are represented, plus a same-trial contrasting pair (SYN-003 vs
SYN-013) to show the matcher actually differentiates based on patient data
rather than giving the same answer regardless of input.

## Methodology (please read before reviewing labels)

- **Deterministic (python-checked) rules**: labeled by actually running your
  real `check_python_rule()` / `collapse_logic_groups()` / `summarize()`
  code from `agent2_matcher.py` against the real patient and trial data.
  These aren't a guess -- they're exact, since that logic has no room for
  interpretation. 31/31 of your own unit tests already confirm this code is
  correct in isolation.
- **LLM-checked rules** (the majority -- these trials have 12 to 52 rules
  each, and most are free-text criteria like informed consent, specific
  mutation status, organ function panels, pregnancy, infection history,
  etc.): I read each rule's text against the real patient record and
  labeled it the way a careful human reviewer would -- Met/Not Met only
  when the record actually supports that conclusion, **Unknown whenever the
  patient schema genuinely doesn't capture the needed information** (which
  is most of the time -- your simplified schema tracks biomarkers, stage,
  ECOG, prior treatments, brain mets, 2 lab values, and a few derived
  numbers, not the full clinical picture these real trials ask about).
- **`prior_treatments` is treated as a closed list.** If a specific therapy
  isn't in that list (and the list itself isn't null), I labeled "received
  it" as Not Met / "never received it" as Met, rather than Unknown -- since
  the field is present with concrete content, not missing. Flag this in
  review if you/your team disagree with that assumption; it affects several
  rows.
- One rule (SYN-013 / NCT06756932_13, brain metastases "uncontrolled,
  untreated") is explicitly flagged in the detail file as genuinely
  debatable -- worth discussing as a team rather than just approving.

## A bug this exercise found

Building this test set surfaced a real bug in `collapse_logic_groups()` in
`agent2_matcher.py`: when every rule in a `logic_group` resolves to **Not
Applicable** (e.g. an `applies_if` cohort condition that doesn't apply to a
given patient), the three-valued-OR collapse has no branch for "all NA" and
falls through to its `else: Not Met` branch -- silently turning an
inapplicable cohort requirement into an exclusion. This showed up in the
SYN-005 / NCT05950945 pair (Cohort 3 rules). The overall verdict for that
pair doesn't change (a separate rule already excludes that patient), but the
met/not_met/unknown/na breakdown from a real run of your code will NOT match
this ground-truth row until that function handles the all-NA case. Worth a
quick fix:

```python
if "Met" in outcomes:
    combined = "Met"
elif "Unknown" in outcomes:
    combined = "Unknown"
elif all(o == "Not Applicable" for o in outcomes):
    combined = "Not Applicable"
else:
    combined = "Not Met"
```

## Why there's no "Likely Eligible" example

All 10 pairs land on "Excluded" or "Needs Review" -- none on "Likely
Eligible". That's not a selection bias; given how many of each trial's rules
are free-text administrative/clinical-detail criteria your simplified
patient schema just doesn't capture, almost every real combination ends up
with at least one genuine Unknown, which blocks "Likely Eligible" by
design. Worth noting as a finding in your evaluation report rather than
something to "fix" by picking easier pairs.

## Next steps for your team

1. Open `ground_truth_test_set.csv`, read the matching rows in
   `ground_truth_rule_level_detail.csv` for anything that looks off.
2. Each reviewer fills in `reviewed_by` and `reviewer_agrees` (yes/no) per
   row, with `review_notes` for anything they'd change.
3. Once agreed, this becomes your saved ground-truth set -- you can then run
   Agent 2 on just these 10 pairs and diff its `match_results.csv` output
   against `ground_truth_test_set.csv` to measure actual accuracy.
