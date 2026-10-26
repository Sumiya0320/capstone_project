"""Dependency-free metrics. No model calls or automatic reference labels."""

LABELS = ("Met", "Not Met", "Unknown", "Not Applicable")
VERDICTS = ("Likely Eligible", "Excluded", "Needs Review")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def approved(row):
    return (
        row.get("review_status") == "verified"
        and bool(row.get("reviewed_by", "").strip())
        and bool(row.get("reference_evidence", "").strip())
        and row.get("independent") == "yes"
    )


def technical_failure(reason):
    text = reason.lower()
    return any(marker in text for marker in (
        "api error", "llm not configured", "unrecognized operator",
        "unsupported operator", "error evaluating",
        "could not compare", "typeerror", "llm call failed", "api failure",
    ))


def classification(cases, labels=LABELS):
    """Missing/technical predictions are errors, retained in the denominator."""
    matrix = {label: {p: 0 for p in (*labels, "Technical/Missing")} for label in labels}
    for expected, predicted, failure in cases:
        if expected not in labels:
            raise ValueError(f"Invalid reference class: {expected}")
        column = predicted if not failure and predicted in labels else "Technical/Missing"
        matrix[expected][column] += 1
    total = len(cases)
    correct = sum(matrix[label][label] for label in labels)
    classes = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(matrix[actual][label] for actual in labels)
        classes[label] = {
            "support": support, "predicted": predicted, "correct": tp,
            "precision": ratio(tp, predicted), "recall": ratio(tp, support),
            "f1": ratio(2 * tp, support + predicted),
        }
    return {
        "status": "Evaluated" if total else "Not Yet Evaluated",
        "total": total, "correct": correct, "incorrect": total - correct,
        "accuracy": ratio(correct, total), "per_class": classes,
        "confusion_matrix": matrix,
    }


def extraction(reference_ids, judgments):
    """Judgments map each extracted rule to one reference ID, or empty for FP.

    A duplicate extraction of an already matched reference is a false positive.
    Human matching must assess semantics, polarity, thresholds and conditions.
    """
    references = set(reference_ids)
    matched = set()
    for reference_id in judgments:
        if reference_id:
            if reference_id not in references:
                raise ValueError(f"Unknown reference ID: {reference_id}")
            matched.add(reference_id)
    tp = len(matched)
    fp = len(judgments) - tp
    fn = len(references - matched)
    return {
        "correctly_extracted": tp, "missing": fn, "incorrect_or_unsupported": fp,
        "reference_rules": len(references), "extracted_rules": len(judgments),
        "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }
