"""Prepare and evaluate the three existing DCIS cases; live collection is explicit."""

import argparse
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

import run_evaluation as evaluation
from metrics import LABELS, VERDICTS, approved, technical_failure

ROOT = evaluation.ROOT
PACK = ROOT / "evaluation/dcis"
TRIAL = "NCT04916808"
PATIENT_IDS = ("SYN-DCIS-ELIGIBLE", "SYN-DCIS-EXCLUDED", "SYN-DCIS-REVIEW")
FIELDS = ("patient_id", "trial_id", "rule_id", "rule_text", "expected_result", "unknown_cause",
          "patient_sha256", "rules_sha256", *evaluation.REVIEW)
SCORES = ("correctness_0_2", "decision_consistency_0_2", "grounding_0_2",
          "missing_information_0_2", "unsupported_assumptions_0_2")
# Fixed before predictions: four cases per patient, targeting distinct rule features.
SAMPLE = ((PATIENT_IDS[0], "03"), (PATIENT_IDS[0], "09"), (PATIENT_IDS[0], "13"), (PATIENT_IDS[0], "20"),
          (PATIENT_IDS[1], "07"), (PATIENT_IDS[1], "08"), (PATIENT_IDS[1], "16"), (PATIENT_IDS[1], "19"),
          (PATIENT_IDS[2], "02"), (PATIENT_IDS[2], "08"), (PATIENT_IDS[2], "10"), (PATIENT_IDS[2], "15"))


def save_once(path, rows, fields):
    if not path.exists():
        evaluation.write_csv(path, rows, fields)


def inputs():
    rule_path = ROOT / "data/rules/drafts" / f"{TRIAL}.json"
    rules = json.loads(rule_path.read_text(encoding="utf-8"))["rules"]
    patients = {p["patient_id"]: p for p in json.loads(
        (ROOT / "synthetic patient/synthetic_patients_simple.json").read_text(encoding="utf-8"))}
    return rule_path, rules, {key: patients[key] for key in PATIENT_IDS}


def source_clauses(text):
    result = []
    kind = ""
    for line in text.splitlines():
        if line.startswith("Inclusion Criteria:"):
            kind = "IN"
        elif line.startswith("Exclusion Criteria:"):
            kind = "EX"
        elif match := re.match(r"^(\d+)\.\s+(.*)", line):
            result.append({"source_clause_id": f"{kind}-{match[1]}", "source_quote": match[2]})
    return result


def prepare():
    labels = PACK / "labels"
    labels.mkdir(parents=True, exist_ok=True)
    rule_path, rules, patients = inputs()
    source_path = PACK / "source/NCT04916808.registry.json"
    registry = json.loads(source_path.read_text(encoding="utf-8"))
    protocol = registry["protocolSection"]
    if protocol["identificationModule"]["nctId"] != TRIAL:
        raise ValueError("Wrong registry trial")
    clauses = source_clauses(protocol["eligibilityModule"]["eligibilityCriteria"])
    source_text = PACK / "source/criteria.txt"
    if not source_text.exists():
        source_text.write_text(protocol["eligibilityModule"]["eligibilityCriteria"] + "\n", encoding="utf-8")
    save_once(PACK / "source/source_clauses.csv", clauses, ("source_clause_id", "source_quote"))
    snapshot = PACK / "patient_profiles.json"
    if not snapshot.exists():
        snapshot.write_text(json.dumps(list(patients.values()), indent=2), encoding="utf-8")
    extraction_snapshot = PACK / "extracted_rules.json"
    if not extraction_snapshot.exists():
        extraction_snapshot.write_bytes(rule_path.read_bytes())
    if (json.loads(snapshot.read_text(encoding="utf-8")) != list(patients.values())
            or evaluation.digest(extraction_snapshot) != evaluation.digest(rule_path)
            or source_text.read_text(encoding="utf-8") != protocol["eligibilityModule"]["eligibilityCriteria"] + "\n"):
        raise ValueError("Readable source/patient/rule snapshots changed; restore the frozen pack before review")
    manifest_path = PACK / "input_manifest.json"
    manifest = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_url": f"https://clinicaltrials.gov/api/v2/studies/{TRIAL}",
        "registry_last_update": protocol["statusModule"]["lastUpdatePostDateStruct"]["date"],
        "source_sha256": evaluation.digest(source_path), "rules_sha256": evaluation.digest(rule_path),
        "patient_sha256": {key: evaluation.object_hash(value) for key, value in patients.items()},
        "explanation_sample": [{"patient_id": p, "rule_id": f"{TRIAL}_{r}"} for p, r in SAMPLE],
        "warning": "No labels in this pack have been independently assigned by humans yet.",
    }
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("source_sha256", "rules_sha256", "patient_sha256"):
        if stored[field] != manifest[field]:
            raise ValueError(f"Frozen DCIS input changed: {field}. Archive and re-review; do not overwrite hashes.")
    save_once(labels / "agent1_reference.csv", [], (
        "trial_id", "reference_id", "reference_rule", "source_quote", *evaluation.REVIEW))
    save_once(labels / "agent1_trials.csv", [{
        "trial_id": TRIAL, "rules_sha256": evaluation.digest(rule_path),
        "source_file": str(source_path.relative_to(ROOT)), "source_sha256": evaluation.digest(source_path),
        "reference_complete": "no", "review_status": "unreviewed",
    }], ("trial_id", "rules_sha256", "source_file", "source_sha256", "reference_complete", *evaluation.REVIEW))
    matches = []
    for rule in rules:
        # Exact-text source linkage is a navigational aid, never an equivalence label.
        candidates = [c for c in clauses if c["source_quote"] == rule["source_text"]]
        matches.append({**rule, "trial_id": TRIAL, "reference_id": "", "review_status": "unreviewed",
                        "candidate_source_clause": ";".join(c["source_clause_id"] for c in candidates)})
    save_once(labels / "agent1_matches.csv", matches, (
        "trial_id", "rule_id", "rule_text", "type", "field", "operator", "value", "applies_if", "logic_group",
        "candidate_source_clause", "source_text", "reference_id", *evaluation.REVIEW))
    for reviewer in ("student_1", "student_2"):
        save_once(labels / f"agent1_source_review_{reviewer}.csv", [{**c, "reviewer": ""} for c in clauses], (
            "source_clause_id", "source_quote", "atomic_reference_rules", "logical_structure",
            "exceptions_and_thresholds", "reviewer", "notes"))
    references = [{
        "patient_id": pid, "trial_id": TRIAL, "rule_id": rule["rule_id"], "rule_text": rule["rule_text"],
        "patient_sha256": evaluation.object_hash(patient), "rules_sha256": evaluation.digest(rule_path),
        "review_status": "unreviewed", "expected_result": "",
    } for pid, patient in patients.items() for rule in rules]
    save_once(labels / "agent2_reference.csv", references, (*FIELDS, "adjudication_notes"))
    for reviewer in ("student_3", "student_4"):
        save_once(labels / f"agent2_blind_{reviewer}.csv", references, FIELDS)
    verdicts = [{"patient_id": pid, "trial_id": TRIAL,
                 "patient_sha256": evaluation.object_hash(patient), "rules_sha256": evaluation.digest(rule_path),
                 "review_status": "unreviewed"} for pid, patient in patients.items()]
    save_once(labels / "patient_reference.csv", verdicts, (
        "patient_id", "trial_id", "expected_overall", "patient_sha256", "rules_sha256", *evaluation.REVIEW))
    save_once(labels / "explanation_review.csv", [{
        "patient_id": p, "trial_id": TRIAL, "rule_id": f"{TRIAL}_{r}", "review_slot": reviewer,
    } for p, r in SAMPLE for reviewer in ("student_3", "student_4")], (
        "patient_id", "trial_id", "rule_id", "review_slot", "prediction_sha256", *SCORES, "reviewer", "notes"))
    refresh_tables()
    print("Prepared DCIS pack: 20 extracted rules, 60 human reference rows, 3 verdicts, 12 explanation cases (24 ratings).")


def predictions():
    path = PACK / "predictions/pipeline_predictions.json"
    if not path.exists():
        return {}, ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    indexed = {}
    _, rules, patients = inputs()
    for record in payload["records"]:
        if record["trial_id"] != TRIAL or record["patient_id"] not in patients:
            raise ValueError("Predictions outside DCIS cohort")
        if (record.get("patient_sha256") != evaluation.object_hash(patients[record["patient_id"]])
                or record["agent1"].get("rules") != rules):
            raise ValueError("Prediction inputs do not match the frozen DCIS cohort")
        for rule in record["agent2"].get("results", []):
            key = (record["patient_id"], rule["rule_id"])
            if key in indexed:
                raise ValueError("Duplicate DCIS prediction")
            indexed[key] = rule
    return indexed, evaluation.digest(path)


def refresh_tables():
    indexed, prediction_hash = predictions()
    _, rules, patients = inputs()
    by_id = {r["rule_id"]: r for r in rules}
    references = evaluation.read_csv(PACK / "labels/agent2_reference.csv")
    tables = PACK / "coordinator_only"
    tables.mkdir(exist_ok=True)
    rows = []
    for row in references:
        predicted = indexed.get((row["patient_id"], row["rule_id"]), {})
        rule = by_id[row["rule_id"]]
        patient = patients[row["patient_id"]]
        rows.append({**row, "rule_type": rule["type"], "logic_group": rule.get("logic_group"),
                     "patient_evidence": json.dumps(patient, sort_keys=True),
                     "actual_prediction": predicted.get("result", "Not collected"),
                     "prediction_reason": predicted.get("reason", "No saved rule-level prediction"),
                     "technical_or_missing_prediction": not predicted or technical_failure(predicted.get("reason", "")),
                     "prediction_sha256": prediction_hash})
    fields = ("patient_id", "trial_id", "rule_id", "rule_type", "rule_text", "logic_group",
              "patient_evidence", "expected_result", "review_status", "actual_prediction", "prediction_reason",
              "technical_or_missing_prediction", "prediction_sha256")
    evaluation.write_csv(tables / "agent2_review_table.csv", rows, fields)
    # Only a review candidate, not an expected Unknown label. Keep other prediction Unknowns visible too.
    focus = [r for r in rows if (r["patient_id"] == PATIENT_IDS[2] and r["rule_id"].endswith("_08"))
             or r["actual_prediction"] == "Unknown" or r["expected_result"] == "Unknown"]
    evaluation.write_csv(tables / "missing_information_review.csv", focus, fields)
    sample_keys = {(p, f"{TRIAL}_{r}") for p, r in SAMPLE}
    evaluation.write_csv(tables / "explanation_sample.csv", [r for r in rows if (r["patient_id"], r["rule_id"]) in sample_keys], fields)


def collect():
    prepare()
    output = PACK / "predictions/pipeline_predictions.json"
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        raise ValueError("Predictions already frozen. Refusing paid rerun/overwrite; use refresh to rebuild review tables.")
    _, _, patients = inputs()
    evaluation.collect(evaluation.read_csv(PACK / "labels/agent2_reference.csv"), patients, output)
    refresh_tables()
    print("Saved actual DCIS predictions and explanations. Human expected labels remain blank.")


def explanation_metrics():
    indexed, prediction_hash = predictions()
    references = {(r["patient_id"], r["rule_id"]): r for r in evaluation.read_csv(PACK / "labels/agent2_reference.csv")}
    reviews = evaluation.read_csv(PACK / "labels/explanation_review.csv")
    grouped = {}
    for row in reviews:
        key = (row["patient_id"], row["rule_id"])
        if key not in {(p, f"{TRIAL}_{r}") for p, r in SAMPLE}:
            raise ValueError("Unexpected explanation sample case")
        if not row.get("reviewer") or row.get("prediction_sha256") != prediction_hash or not prediction_hash:
            continue
        if not approved(references[key]) or key not in indexed:
            continue
        if any(row.get(s) not in ("0", "1", "2") for s in SCORES):
            continue
        grouped.setdefault(key, []).append(row)
    paired = {k: v for k, v in grouped.items() if len(v) == 2 and len({r["reviewer"] for r in v}) == 2
              and {r["review_slot"] for r in v} == {"student_3", "student_4"}}
    dimensions = {}
    for score in SCORES:
        values = [int(r[score]) for rows in paired.values() for r in rows]
        dimensions[score] = {
            "ratings": len(values), "distribution": {str(n): values.count(n) for n in (0, 1, 2)},
            "mean": sum(values) / len(values) if values else None,
            "exact_interreviewer_agreement": sum(rows[0][score] == rows[1][score] for rows in paired.values()) / len(paired) if paired else None,
        }
    return {"status": "Evaluated" if paired else "Not Yet Evaluated", "paired_cases": len(paired),
            "planned_cases": len(SAMPLE), "dimensions": dimensions,
            "limitation": "Purposive sample from three controlled synthetic patients; no population-level generalisation or composite score."}


def evaluate():
    prepare()
    output = PACK / "predictions/pipeline_predictions.json"
    if not output.exists():
        raise ValueError("No saved DCIS predictions. Run collect once (paid) or import a matching full pipeline export.")
    references = evaluation.read_csv(PACK / "labels/agent2_reference.csv")
    rule_path, rules, patients = inputs()
    expected_keys = {(p, TRIAL, r["rule_id"]) for p in patients for r in rules}
    if set(evaluation.unique(references, ("patient_id", "trial_id", "rule_id"))) != expected_keys:
        raise ValueError("Final reference cohort must contain exactly the 60 frozen DCIS cases")
    if any(not approved(r) or r["expected_result"] not in LABELS for r in references):
        raise ValueError("All 60 DCIS rule labels require independent human adjudication before final evaluation.")
    # Require two separately authored blind labels, or an explicit adjudication for disagreements.
    blind = [evaluation.unique(evaluation.read_csv(PACK / f"labels/agent2_blind_{slot}.csv"),
                               ("patient_id", "trial_id", "rule_id")) for slot in ("student_3", "student_4")]
    for row in references:
        key = (row["patient_id"], row["trial_id"], row["rule_id"])
        a, b = (r.get(key, {}) for r in blind)
        if (not approved(a) or not approved(b) or a["reviewed_by"] == b["reviewed_by"]
                or a.get("expected_result") not in LABELS or b.get("expected_result") not in LABELS):
            raise ValueError(f"Two named independent blind reviews required: {key}")
        if (a["expected_result"] != b["expected_result"] or row["expected_result"] != a["expected_result"]
                or a.get("unknown_cause") != b.get("unknown_cause")
                or row.get("unknown_cause") != a.get("unknown_cause")) and not row.get("adjudication_notes", "").strip():
            raise ValueError(f"Document disagreement adjudication: {key}")
        for label in (row, a, b):
            if (label.get("patient_sha256") != evaluation.object_hash(patients[row["patient_id"]])
                    or label.get("rules_sha256") != evaluation.digest(rule_path)):
                raise ValueError(f"Stale human reference input: {key}")
    trial_rows = evaluation.read_csv(PACK / "labels/agent1_trials.csv")
    reference_rows = evaluation.read_csv(PACK / "labels/agent1_reference.csv")
    extraction_rows = evaluation.read_csv(PACK / "labels/agent1_matches.csv")
    if (len(trial_rows) != 1 or not approved(trial_rows[0]) or trial_rows[0]["reference_complete"] != "yes"
            or not reference_rows or any(not approved(r) or not r["reference_rule"].strip() or not r["reference_id"].strip() for r in reference_rows)
            or any(not approved(r) for r in extraction_rows)):
        raise ValueError("Complete independent Agent 1 references, every extraction judgment, and trial approval")
    trial = trial_rows[0]
    source_path = PACK / "source/NCT04916808.registry.json"
    if (trial["trial_id"] != TRIAL or trial["rules_sha256"] != evaluation.digest(rule_path)
            or trial["source_sha256"] != evaluation.digest(source_path)
            or (ROOT / trial["source_file"]).resolve() != source_path.resolve()
            or any(r["trial_id"] != TRIAL for r in (*reference_rows, *extraction_rows))):
        raise ValueError("Agent 1 source, rules or scope differs from the frozen pack")
    if set(evaluation.unique(extraction_rows, ("rule_id",))) != {(r["rule_id"],) for r in rules}:
        raise ValueError("All 20 DCIS extraction judgments are required")
    source = json.loads((PACK / "source/NCT04916808.registry.json").read_text(encoding="utf-8"))
    criteria = source["protocolSection"]["eligibilityModule"]["eligibilityCriteria"]
    if any(not r["source_quote"].strip() or r["source_quote"] not in criteria for r in reference_rows):
        raise ValueError("Each independent reference needs an exact quote from the saved original criteria")
    source_reviewers = []
    for slot in ("student_1", "student_2"):
        rows = evaluation.read_csv(PACK / f"labels/agent1_source_review_{slot}.csv")
        if ({r["source_clause_id"] for r in rows} != {c["source_clause_id"] for c in source_clauses(criteria)}
                or any(not r["atomic_reference_rules"].strip() or not r["reviewer"].strip() for r in rows)):
            raise ValueError("Two complete independently authored source-clause reviews are required")
        source_reviewers.append({r["reviewer"] for r in rows})
    if source_reviewers[0] & source_reviewers[1]:
        raise ValueError("Source reviewers must be distinct people")
    verdicts = evaluation.read_csv(PACK / "labels/patient_reference.csv")
    if (set(evaluation.unique(verdicts, ("patient_id",))) != {(p,) for p in patients}
            or any(not approved(r) or r["expected_overall"] not in VERDICTS for r in verdicts)):
        raise ValueError("All three independently reviewed patient verdicts are required")
    if any(r["trial_id"] != TRIAL or r["patient_sha256"] != evaluation.object_hash(patients[r["patient_id"]])
           or r["rules_sha256"] != evaluation.digest(rule_path) for r in verdicts):
        raise ValueError("Patient-verdict references differ from frozen inputs")
    explanation = explanation_metrics()
    if explanation["paired_cases"] != len(SAMPLE):
        raise ValueError("Complete both independent explanation ratings for all 12 fixed cases")
    args = argparse.Namespace(labels_dir=PACK / "labels", results_dir=PACK / "results", trial_id=TRIAL,
                              collect=False, run_dcis=False, predictions=output)
    exit_code = evaluation.run(args)
    path = PACK / "results/explanation_evaluation.json"
    path.write_text(json.dumps(explanation, indent=2), encoding="utf-8")
    summary_path = PACK / "results/evaluation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["explanations"] = explanation
    summary["scope"] = "NCT04916808 only; 3 controlled synthetic patients, not an external validation cohort"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for name in ("evaluation_report.md", "capstone_evaluation_section.md"):
        report = PACK / "results" / name
        text = report.read_text(encoding="utf-8")
        for phrase in ("Explanation quality remains Not Yet Evaluated.", "Explanations remain Not Yet Evaluated."):
            text = text.replace(phrase, f"Explanation quality: {explanation['status']} ({explanation['paired_cases']}/{len(SAMPLE)} paired human-reviewed cases; see explanation_evaluation.json).")
        text = text.replace("Evaluation is incomplete.",
                            "The scoped DCIS human review is complete; this does not verify historical multi-trial claims.")
        report.write_text(text, encoding="utf-8")
    print(f"Explanation paired cases: {explanation['paired_cases']}/{len(SAMPLE)}. See {path.relative_to(ROOT)}")
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "refresh", "collect", "evaluate"))
    args = parser.parse_args()
    try:
        if args.command == "evaluate":
            raise SystemExit(evaluate())
        {"prepare": prepare, "refresh": refresh_tables, "collect": collect}[args.command]()
    except (ValueError, FileNotFoundError) as error:
        print(f"Review not ready: {error}", file=sys.stderr)
        raise SystemExit(1)
