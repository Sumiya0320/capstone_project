
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "rules" / "drafts"
APPROVED_DIR = ROOT / "data" / "rules" / "raw"

VALID_OPERATORS = {
    ">=", "<=", ">", "<", "==", "!=", "in", "not_in"
}


def validate_draft(trial_id):
    """Validate a draft's basic structure before approval."""

    draft_path = DRAFT_DIR / f"{trial_id}.json"

    if not draft_path.is_file():
        raise FileNotFoundError(f"Draft not found: {trial_id}")

    data = json.loads(draft_path.read_text(encoding="utf-8"))

    if data.get("trial_id") != trial_id:
        raise ValueError("Trial ID does not match the filename.")

    rules = data.get("rules")

    if not isinstance(rules, list) or not rules:
        raise ValueError("Draft contains no eligibility rules.")

    seen_ids = set()

    for rule in rules:
        rule_id = rule.get("rule_id")

        if not rule_id or rule_id in seen_ids:
            raise ValueError(f"Missing or duplicate rule ID: {rule_id}")

        seen_ids.add(rule_id)

        if rule.get("type") not in ("inclusion", "exclusion"):
            raise ValueError(f"Invalid rule type: {rule_id}")

        if rule.get("check_method") not in ("python", "llm"):
            raise ValueError(f"Invalid check method: {rule_id}")

        if not rule.get("rule_text") or not rule.get("source_text"):
            raise ValueError(f"Missing rule text: {rule_id}")

        if rule["check_method"] == "python":
            if rule.get("operator") not in VALID_OPERATORS:
                raise ValueError(f"Unsupported operator: {rule_id}")

            if not rule.get("field") or rule.get("value") is None:
                raise ValueError(f"Incomplete Python rule: {rule_id}")

    return data


def approve_draft(trial_id, reviewed=False):
    """
    Activate a validated draft after explicit human review.

    Approval does not establish clinical correctness.
    """

    if reviewed is not True:
        raise PermissionError(
            "Explicit human review confirmation is required."
        )

    validate_draft(trial_id)

    APPROVED_DIR.mkdir(parents=True, exist_ok=True)

    source = DRAFT_DIR / f"{trial_id}.json"
    destination = APPROVED_DIR / f"{trial_id}.json"

    if destination.exists():
        raise FileExistsError(
            f"Active rules already exist for {trial_id}."
        )

    shutil.copy2(source, destination)

    return destination
