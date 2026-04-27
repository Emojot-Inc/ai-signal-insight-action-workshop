import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError


dynamodb_resource = boto3.resource("dynamodb")


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


def persist_action_result(complaint_id, action_result):
    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    table.update_item(
        Key={"complaintId": complaint_id},
        UpdateExpression=(
            "SET actionMode = :actionMode, "
            "shouldEscalate = :shouldEscalate, "
            "actionReasons = :actionReasons, "
            "simulatedAction = :simulatedAction, "
            "actionProcessedAt = :actionProcessedAt, "
            "processingStatus = :processingStatus"
        ),
        ExpressionAttributeValues={
            ":actionMode": action_result["actionMode"],
            ":shouldEscalate": action_result["shouldEscalate"],
            ":actionReasons": action_result["reasons"],
            ":simulatedAction": action_result["simulatedAction"],
            ":actionProcessedAt": action_result["processedAt"],
            ":processingStatus": action_result["processingStatus"],
        },
        ConditionExpression="attribute_exists(complaintId)",
    )


def persist_failure_status(complaint_id, processing_status):
    if not complaint_id:
        return

    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    table.update_item(
        Key={"complaintId": complaint_id},
        UpdateExpression="SET processingStatus = :processingStatus",
        ExpressionAttributeValues={":processingStatus": processing_status},
        ConditionExpression="attribute_exists(complaintId)",
    )


def lambda_handler(event, _context):
    now = datetime.now(timezone.utc).isoformat()
    action_mode = os.getenv("ACTION_MODE", "simulate")
    analysis = normalize_detail(event)

    try:
        decision = evaluate_escalation_rules(analysis)

        simulated_action = "escalate_case" if decision["shouldEscalate"] else "no_escalation"
        processing_status = "ACTIONED"

        result = {
            "status": "ok",
            "complaintId": analysis["complaintId"],
            "actionMode": action_mode,
            "shouldEscalate": decision["shouldEscalate"],
            "reasons": decision["reasons"],
            "simulatedAction": simulated_action,
            "processingStatus": processing_status,
            "processedAt": now,
        }
        persist_action_result(analysis["complaintId"], result)

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

        return result
    except (ClientError, BotoCoreError) as exc:
        log(
            "ERROR",
            "Action persistence failed",
            complaintId=analysis["complaintId"],
            errorType=type(exc).__name__,
            error=str(exc),
        )
        try:
            persist_failure_status(analysis["complaintId"], "FAILED_ACTION")
        except (ClientError, BotoCoreError):
            log(
                "WARNING",
                "Failed to persist action failure status",
                complaintId=analysis["complaintId"],
            )
        raise
    except Exception as exc:
        log(
            "ERROR",
            "Action unexpected failure",
            complaintId=analysis["complaintId"],
            errorType=type(exc).__name__,
            error=str(exc),
        )
        try:
            persist_failure_status(analysis["complaintId"], "FAILED_ACTION")
        except (ClientError, BotoCoreError):
            log(
                "WARNING",
                "Failed to persist action failure status",
                complaintId=analysis["complaintId"],
            )
        raise
