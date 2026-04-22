import json
import os
from datetime import datetime, timezone


def log(level, message, **fields):
    print(json.dumps({"level": level, "message": message, **fields}))


def normalize_detail(event):
    detail = event.get("detail", {})
    return {
        "complaintId": detail.get("complaintId", "unknown"),
        "urgency": str(detail.get("urgency", "")).lower(),
        "sentiment": str(detail.get("sentiment", "")).lower(),
        "category": str(detail.get("category", "")).lower(),
        "piiDetected": bool(detail.get("piiDetected", False)),
    }


def _is_enabled(env_name, default=True):
    value = os.getenv(env_name, str(default).lower()).strip().lower()
    return value in {"1", "true", "yes", "on"}


def evaluate_escalation_rules(analysis):
    reasons = []

    if _is_enabled("RULE_URGENCY_HIGH", True) and analysis["urgency"] == "high":
        reasons.append("urgency_high")

    if _is_enabled("RULE_NEGATIVE_COMPLIANCE", True):
        if analysis["sentiment"] == "negative" and analysis["category"] == "compliance":
            reasons.append("negative_compliance")

    if _is_enabled("RULE_PII_AND_NOT_LOW", True):
        if analysis["piiDetected"] and analysis["urgency"] != "low":
            reasons.append("pii_and_urgency_not_low")

    return {"shouldEscalate": len(reasons) > 0, "reasons": reasons}


def lambda_handler(event, _context):
    now = datetime.now(timezone.utc).isoformat()
    action_mode = os.getenv("ACTION_MODE", "simulate")
    analysis = normalize_detail(event)
    decision = evaluate_escalation_rules(analysis)

    simulated_action = "escalate_case" if decision["shouldEscalate"] else "no_escalation"
    processing_status = "SIMULATED_ESCALATION" if decision["shouldEscalate"] else "SIMULATED_NO_ACTION"

    log(
        "INFO",
        "Action evaluated",
        complaintId=analysis["complaintId"],
        actionMode=action_mode,
        urgency=analysis["urgency"],
        sentiment=analysis["sentiment"],
        category=analysis["category"],
        piiDetected=analysis["piiDetected"],
        shouldEscalate=decision["shouldEscalate"],
        reasons=decision["reasons"],
        simulatedAction=simulated_action,
        processingStatus=processing_status,
        processedAt=now,
    )

    return {
        "status": "ok",
        "complaintId": analysis["complaintId"],
        "actionMode": action_mode,
        "shouldEscalate": decision["shouldEscalate"],
        "reasons": decision["reasons"],
        "simulatedAction": simulated_action,
        "processingStatus": processing_status,
        "processedAt": now,
    }
