"""Offline by default; --collect and --run-dcis explicitly enable paid calls."""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from metrics import LABELS, VERDICTS, approved, classification, extraction, ratio, technical_failure

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
REVIEW = ("review_status", "reviewed_by", "independent", "reference_evidence")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def unique(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[f] for f in fields)
        if key in result:
            raise ValueError(f"Duplicate key {key}")
        result[key] = row
    return result


def inventory():
    files = {p.stem: p for p in sorted((ROOT / "data/rules/raw").glob("*.json"))}
    files.update({p.stem: p for p in sorted((ROOT / "data/rules/drafts").glob("*.json"))})
    return files


def prepare(files, patients):
    """Create review templates once; never overwrite completed human labels."""
    labels = HERE / "labels"
    labels.mkdir(exist_ok=True)
    draft = read_csv(HERE / "ground_truth_rule_level_detail.csv")
    rows = []
    for row in draft:
        rows.append({
            **row, "review_status": "unreviewed", "reviewed_by": "", "independent": "",
            "reference_evidence": "", "unknown_cause": "",
            "patient_sha256": object_hash(patients[row["patient_id"]]),
            "rules_sha256": digest(files[row["trial_id"]]),
        })
    templates = {
        "agent2_reference.csv": (rows, (
            "patient_id", "trial_id", "rule_id", "rule_text", "expected_result", "reasoning", "source",
            "unknown_cause", "patient_sha256", "rules_sha256", *REVIEW,
        )),
        "patient_reference.csv": ([{
            **r, "review_status": "unreviewed", "reviewed_by": "", "independent": "",
            "reference_evidence": "", "patient_sha256": object_hash(patients[r["patient_id"]]),
            "rules_sha256": digest(files[r["trial_id"]]),
        } for r in read_csv(HERE / "ground_truth_test_set.csv")], (
            "patient_id", "trial_id", "expected_overall", "patient_sha256", "rules_sha256", *REVIEW,
        )),
        "agent1_reference.csv": ([], (
            "trial_id", "reference_id", "reference_rule", "source_quote", *REVIEW,
        )),
        "agent1_trials.csv": ([{
            "trial_id": tid, "rules_sha256": digest(path),
            "source_file": f"data/trials/{tid}.json",
            "source_sha256": digest(ROOT / "data/trials" / f"{tid}.json"),
            "reference_complete": "no", "review_status": "unreviewed",
        } for tid, path in files.items()], (
            "trial_id", "rules_sha256", "source_file", "source_sha256", "reference_complete", *REVIEW,
        )),
        "agent1_matches.csv": ([{
            "trial_id": tid, "rule_id": rule["rule_id"], "rule_text": rule["rule_text"],
            "reference_id": "", "review_status": "unreviewed",
        } for tid, path in files.items() for rule in json.loads(path.read_text(encoding="utf-8"))["rules"]], (
            "trial_id", "rule_id", "rule_text", "reference_id", *REVIEW,
        )),
    }
    for name, (rows, fields) in templates.items():
        path = labels / name
        if not path.exists():
            write_csv(path, rows, fields)


def collect(references, patients, output):
    from integration.agent_connector import run_full_pipeline
    pairs = sorted({(r["patient_id"], r["trial_id"]) for r in references})
    rows = []
    for patient_id, trial_id in pairs:
        print(f"Live API pipeline: {patient_id} / {trial_id}", flush=True)
        result = run_full_pipeline(patients[patient_id], {"trial_id": trial_id})
        rows.append({"patient_id": patient_id, "patient_sha256": object_hash(patients[patient_id]), **result})
    output.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": __import__("agent2_src.agent2_matcher", fromlist=["MODEL"]).MODEL,
        "system_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (
            ROOT / "agent2_src/agent2_matcher.py", ROOT / "integration/agent_connector.py")},
        "records": rows,
    }, indent=2), encoding="utf-8")


def run(args):
    results = (getattr(args, "results_dir", None) or HERE / "results").resolve()
    results.mkdir(exist_ok=True)
    files = inventory()
    patient_path = ROOT / "synthetic patient/synthetic_patients_simple.json"
    patients = {p["patient_id"]: p for p in json.loads(patient_path.read_text(encoding="utf-8"))}
    prepare(files, patients)
    labels = (getattr(args, "labels_dir", None) or HERE / "labels").resolve()
    references = read_csv(labels / "agent2_reference.csv")
    trial_id = getattr(args, "trial_id", None)
    if trial_id:
        references = [r for r in references if r["trial_id"] == trial_id]
    unique(references, ("patient_id", "trial_id", "rule_id"))
    patient_refs = read_csv(labels / "patient_reference.csv")
    if trial_id:
        patient_refs = [r for r in patient_refs if r["trial_id"] == trial_id]
    unique(patient_refs, ("patient_id", "trial_id"))
    tests = subprocess.run(
        [sys.executable, "-B", str(ROOT / "agent2_src/test_agent2_matcher.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    (results / "unit_tests.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    test_counts = re.search(r"(\d+) passed, (\d+) failed out of (\d+) tests", tests.stdout)
    unit_counts = dict(zip(("passed", "failed", "total"), map(int, test_counts.groups()))) if test_counts else {}
    dcis = {"status": "Not run (requires paid API calls)"}
    dcis_record = results / "dcis_validation.json"
    if not args.run_dcis and dcis_record.exists():
        dcis = json.loads(dcis_record.read_text(encoding="utf-8"))
        dcis["note"] = "Saved live smoke run; not rerun by this offline invocation."
        if (dcis.get("patient_file_sha256") != digest(patient_path)
                or dcis.get("rules_sha256") != digest(files["NCT04916808"])):
            dcis["status"] = "Saved run is stale; current inputs not validated"
    if args.run_dcis:
        command = subprocess.run([sys.executable, "-B", str(ROOT / "validate_dcis_pipeline.py")],
                                 cwd=ROOT, capture_output=True, text=True)
        (results / "dcis_validation.txt").write_text(command.stdout + command.stderr, encoding="utf-8")
        dcis = {"status": "Passed" if command.returncode == 0 else "Failed", "exit_code": command.returncode,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "patient_file_sha256": digest(patient_path),
                "rules_sha256": digest(files["NCT04916808"]),
                "transcript_sha256": digest(results / "dcis_validation.txt"),
                "interpretation": "Three controlled patient-level smoke cases; not independent ground truth."}
        dcis_record.write_text(json.dumps(dcis, indent=2), encoding="utf-8")
    prediction_path = args.predictions or results / "pipeline_predictions.json"
    if args.collect:
        collect(references, patients, prediction_path)
    predictions, verdict_predictions = {}, {}
    if prediction_path.exists():
        payload = json.loads(prediction_path.read_text(encoding="utf-8"))
        for record in payload["records"]:
            pair = (record["patient_id"], record["trial_id"])
            if pair in verdict_predictions:
                raise ValueError(f"Duplicate prediction pair: {pair}")
            stage = record["agent2"]
            failed = record["agent1"].get("status") != "success" or stage.get("status") != "success"
            rule_hash = object_hash(record["agent1"].get("rules", []))
            current_rules = json.loads(files[pair[1]].read_text(encoding="utf-8"))["rules"]
            stale = (rule_hash != object_hash(current_rules)
                     or record.get("patient_sha256") != object_hash(patients[pair[0]]))
            expected_ids = {r["rule_id"] for r in current_rules}
            actual_ids = {r["rule_id"] for r in stage.get("results", [])}
            incomplete = actual_ids != expected_ids
            for rule in stage.get("results", []):
                key = (*pair, rule["rule_id"])
                if key in predictions:
                    raise ValueError(f"Duplicate prediction rule: {key}")
                predictions[key] = (rule.get("result"), failed or stale or not rule.get("reason") or technical_failure(rule.get("reason", "")), rule.get("reason", ""))
            verdict_predictions[pair] = (stage.get("summary", {}).get("overall"), failed or stale or incomplete or not stage.get("results") or any(
                p[1] for key, p in predictions.items() if key[:2] == pair))
    def current(row):
        return (row.get("patient_sha256") == object_hash(patients[row["patient_id"]])
                and row.get("rules_sha256") == digest(files[row["trial_id"]]))
    evaluated, missing_rows, cases = [], [], []
    for row in references:
        if not approved(row) or not current(row):
            continue
        if row["expected_result"] not in LABELS:
            raise ValueError("Invalid verified Agent 2 label")
        if row["expected_result"] == "Unknown" and row["unknown_cause"] not in ("missing_information", "clinical_ambiguity"):
            raise ValueError("Verified Unknown needs an explicit nontechnical cause")
        key = (row["patient_id"], row["trial_id"], row["rule_id"])
        predicted, failed, reason = predictions.get(key, (None, True, "No saved prediction"))
        cases.append((row["expected_result"], predicted, failed))
        item = {**row, "actual": predicted, "technical_or_missing": failed,
                "correct": not failed and predicted == row["expected_result"], "prediction_reason": reason}
        evaluated.append(item)
        if row["expected_result"] == "Unknown" and row["unknown_cause"] == "missing_information":
            missing_rows.append(item)
    a2 = classification(cases)
    verdict_cases = []
    verdict_rows = []
    for row in patient_refs:
        if approved(row) and current(row):
            predicted, failure = verdict_predictions.get((row["patient_id"], row["trial_id"]), (None, True))
            verdict_cases.append((row["expected_overall"], predicted, failure))
            verdict_rows.append({**row, "actual": predicted, "technical_or_missing": failure,
                                 "correct": not failure and predicted == row["expected_overall"]})
    verdicts = classification(verdict_cases, VERDICTS)
    unknown_tp = sum(r["correct"] for r in missing_rows)
    unknown_predicted = [r for r in evaluated if r["actual"] == "Unknown" and not r["technical_or_missing"]]
    missing = {
        "status": "Evaluated" if missing_rows else "Not Yet Evaluated",
        "ground_truth_missing_information": len(missing_rows), "correct_unknown": unknown_tp,
        "unknown_recall": ratio(unknown_tp, len(missing_rows)),
        "unknown_precision_for_missing_information": ratio(unknown_tp, len(unknown_predicted)),
        "predicted_unknown_nontechnical": len(unknown_predicted),
        "all_cause_unknown_precision": a2["per_class"]["Unknown"]["precision"],
        "technical_or_missing_predictions": sum(r["technical_or_missing"] for r in evaluated),
    }
    a1rows = []
    refs = read_csv(labels / "agent1_reference.csv")
    matches = read_csv(labels / "agent1_matches.csv")
    trials = read_csv(labels / "agent1_trials.csv")
    if trial_id:
        trials = [r for r in trials if r["trial_id"] == trial_id]
    unique(refs, ("trial_id", "reference_id"))
    unique(matches, ("trial_id", "rule_id"))
    unique(trials, ("trial_id",))
    for trial in trials:
        tid = trial["trial_id"]
        reference = [r for r in refs if r["trial_id"] == tid]
        judgments = [r for r in matches if r["trial_id"] == tid]
        actual_ids = {r["rule_id"] for r in json.loads(files[tid].read_text(encoding="utf-8"))["rules"]}
        ready = (approved(trial) and trial["reference_complete"] == "yes"
                 and digest(files[tid]) == trial["rules_sha256"]
                 and bool(trial["source_sha256"])
                 and digest(ROOT / trial["source_file"]) == trial["source_sha256"]
                 and bool(reference) and all(approved(r) and r["source_quote"].strip() for r in reference)
                 and all(approved(r) for r in judgments)
                 and {r["rule_id"] for r in judgments} == actual_ids)
        if ready:
            a1rows.append({"trial_id": tid, **extraction(
                [r["reference_id"] for r in reference], [r["reference_id"] for r in judgments])})
    tp = sum(r["correctly_extracted"] for r in a1rows)
    fp = sum(r["incorrect_or_unsupported"] for r in a1rows)
    fn = sum(r["missing"] for r in a1rows)
    a1 = {"status": "Evaluated" if a1rows else "Not Yet Evaluated", "trials": len(a1rows),
          "correctly_extracted": tp, "missing": fn, "incorrect_or_unsupported": fp,
          "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn)}
    write_csv(results / "agent1_evaluation.csv", a1rows, (
        "trial_id", "correctly_extracted", "missing", "incorrect_or_unsupported", "reference_rules", "extracted_rules", "precision", "recall", "f1"))
    write_csv(results / "agent2_evaluation.csv", evaluated, (
        "patient_id", "trial_id", "rule_id", "expected_result", "actual", "correct", "technical_or_missing", "prediction_reason"))
    write_csv(results / "missing_information_evaluation.csv", missing_rows, (
        "patient_id", "trial_id", "rule_id", "expected_result", "actual", "correct", "technical_or_missing", "prediction_reason"))
    write_csv(results / "confusion_matrix.csv", [{"expected": e, **cols} for e, cols in a2["confusion_matrix"].items()], ("expected", *LABELS, "Technical/Missing"))
    write_csv(results / "agent2_per_class.csv", [{"class": k, **v} for k, v in a2["per_class"].items()], ("class", "support", "predicted", "correct", "precision", "recall", "f1"))
    write_csv(results / "patient_verdict_evaluation.csv", verdict_rows, (
        "patient_id", "trial_id", "expected_overall", "actual", "correct", "technical_or_missing"))
    review_path = labels / "explanation_review.csv"
    if not review_path.exists():
        write_csv(review_path, [{**r, "predicted_result": predictions.get((r["patient_id"], r["trial_id"], r["rule_id"]), ("",))[0]} for r in references], (
            "patient_id", "trial_id", "rule_id", "predicted_result", "prediction_sha256",
            "correctness_0_2", "decision_consistency_0_2", "grounding_0_2", "missing_information_0_2",
            "unsupported_assumptions_0_2", "reviewer", "notes"))
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inventory": {"patients": len(patients), "trials": len(files), "draft_rule_labels": len(references),
                      "draft_patient_labels": len(patient_refs), "saved_prediction_rules": len(predictions),
                      "draft_unknown_labels": sum(r["expected_result"] == "Unknown" for r in references),
                      "matcher_derived_draft_labels": sum("real agent2_matcher code" in r.get("source", "") for r in references)},
        "unit_tests": {"exit_code": tests.returncode, "output_file": "unit_tests.txt", **unit_counts},
        "dcis_smoke_test": dcis, "agent1": a1, "agent2": a2, "patient_verdicts": verdicts,
        "missing_information": missing, "explanations": {"status": "Not Yet Evaluated", "method": "Human rubric"},
        "historical_claims": {"Agent 1 94.1%": "Cannot currently verify; extraction accuracy definition and independent references missing",
                              "Agent 2 67.6%": "Cannot currently verify; independently verified rule labels and matching predictions required",
                              "Missing information 97/156 (62.2%)": "Cannot currently verify; independent missing-information labels and predictions required"},
        "input_sha256": {str(p.relative_to(ROOT)): digest(p) for p in [patient_path, *files.values(), *labels.glob("*.csv"),
            *sorted((ROOT / "data/trials").glob("*.json")), ROOT / "agent2_src/agent2_matcher.py", ROOT / "integration/agent_connector.py"]},
        "prediction_sha256": digest(prediction_path),
    }
    (results / "evaluation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    def display(value):
        return "Not Yet Evaluated" if value is None else f"{100 * value:.2f}%"
    report = f"""# Evaluation and Results

The current deterministic Agent 2 unit-test suite {'passed' if tests.returncode == 0 else 'failed'} ({unit_counts.get('passed', 'unparsed')}/{unit_counts.get('total', 'unparsed')} tests). Unit-test pass rates assess implementation behavior and are not estimates of clinical eligibility accuracy. The repository contains {len(patients)} synthetic patients; this evaluation selects {len(references)} patient–rule reference rows and {len(patient_refs)} patient–trial verdict rows. Only explicit, independently verified human references with matching input hashes are eligible. Unreviewed, blank and placeholder approvals are excluded.

| Measurement | Eligible sample size | Correct | Result |
|---|---:|---:|---|
| Agent 1 extraction F1 | {a1['trials']} trials | {tp} rules | {display(a1['f1'])} |
| Agent 2 rule-level accuracy | {a2['total']} rules | {a2['correct']} | {display(a2['accuracy'])} |
| Patient verdict accuracy | {verdicts['total']} pairs | {verdicts['correct']} | {display(verdicts['accuracy'])} |
| Genuine missing-information Unknown recall | {len(missing_rows)} rules | {unknown_tp} | {display(missing['unknown_recall'])} |

Agent 1 precision: {display(a1['precision'])}; recall: {display(a1['recall'])}; missing rules: {fn}; incorrect/unsupported rules: {fp}. Zero counts with zero eligible samples do not indicate zero errors. Unknown precision for missing-information detection: {display(missing['unknown_precision_for_missing_information'])}. All-cause Unknown precision: {display(missing['all_cause_unknown_precision'])}.

DCIS controlled patient-level smoke validation: {dcis['status']}. This checks three deliberately constructed cases, not independent rule-level accuracy. Live tests require paid API calls. Existing match_results.csv contains aggregate counts only and cannot recover individual decisions or technical-error reasons.

The previously reported 94.1% extraction performance, 67.6% rule-level accuracy, and 97/156 (62.2%) missing-information result cannot currently be verified. No independent estimate is reported until reference review is completed. Extraction precision, recall and F1 must not be compared to an undefined historical “accuracy” as if they were identical.

The selected reference rows contain {sum(r['expected_result'] == 'Unknown' for r in references)} proposed Unknown labels and {sum('real agent2_matcher code' in r.get('source', '') for r in references)} explicitly matcher-derived labels. These counts do not establish 97 correct Unknown predictions. No historical rule-level prediction artifact was found in the initial inventory.

## Limitations and required reference work

Independently annotate all atomic inclusion/exclusion criteria from original trial sources, retaining source quotations, logical alternatives, conditions, thresholds and polarity. Confirm complete reference coverage and adjudicate every extracted rule. A source downloaded after extraction must be checked for version differences. Schema validity is not extraction quality.

Independently review the {len(references)} selected rule labels against frozen patient records and criteria, replace circular labels, and document why each Unknown is caused by missing information or clinical ambiguity. Resolve assumptions about treatment-history completeness. Review patient verdicts separately. Export matching uncollapsed rule predictions with error reasons. Technical and missing predictions count as incorrect in the full reference denominator; they never count as successful Unknown predictions. Explain any partial reviewed subset and class imbalance before generalizing.

Explanations remain Not Yet Evaluated. Use the human-review rubric and bind each review to the exact saved prediction hash. No automated explanation score is claimed. Evaluation is incomplete.
"""
    (results / "evaluation_report.md").write_text(report, encoding="utf-8")
    section = f"""# Evaluation and Results

The deterministic Agent 2 unit tests passed {unit_counts.get('passed', 'unparsed')} of {unit_counts.get('total', 'unparsed')} checks. These tests assess implementation correctness rather than clinical eligibility accuracy. The three controlled DCIS integration cases were recorded as: {dcis['status']}. Their expected patient-level outcomes were Likely Eligible, Excluded and Needs Review; this deliberately constructed smoke test does not constitute independent rule-level validation.

The available evaluation dataset contains {len(references)} draft patient–rule labels across {len(patient_refs)} patient–trial pairs, including {sum(r['expected_result'] == 'Unknown' for r in references)} provisional Unknown labels. Placeholder approvals and matcher-derived labels are excluded from independent reference data unless independently re-adjudicated. Agent 1 extraction precision, recall and F1 are {display(a1['precision'])}, {display(a1['recall'])} and {display(a1['f1'])}, respectively ({a1['trials']} independently adjudicated trials). Agent 2 rule-level accuracy is {display(a2['accuracy'])} ({a2['correct']}/{a2['total']} eligible reference decisions); missing-information Unknown recall is {display(missing['unknown_recall'])} ({unknown_tp}/{len(missing_rows)} eligible cases). Zero eligible cases indicate that evaluation has not yet been performed. Explanation quality remains Not Yet Evaluated. The previously reported 94.1%, 67.6% and 97/156 (62.2%) results could not be independently verified. Completing evaluation requires independently adjudicated source-based reference rules and patient–rule labels, matching prediction artifacts, and human explanation review.
"""
    (results / "capstone_evaluation_section.md").write_text(section, encoding="utf-8")
    print(report)
    return tests.returncode or (dcis.get("exit_code", 0) if args.run_dcis else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true", help="PAID: run all draft reference pairs through the real pipeline")
    parser.add_argument("--run-dcis", action="store_true", help="PAID: rerun the three controlled DCIS cases")
    parser.add_argument("--predictions", type=Path, help="Saved full pipeline JSON; no API calls unless --collect is passed")
    parser.add_argument("--labels-dir", type=Path, help="Use a separate independently reviewed reference pack")
    parser.add_argument("--results-dir", type=Path, help="Keep scoped results separate from the original evaluation")
    parser.add_argument("--trial-id", help="Evaluate/collect only this trial")
    raise SystemExit(run(parser.parse_args()))
