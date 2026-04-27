import json
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError


dynamodb_resource = boto3.resource("dynamodb")

RESPONSE_FIELDS = [
    "complaintId",
    "submittedAt",
    "channel",
    "processingStatus",
    "sentiment",
    "urgency",
    "category",
    "piiDetected",
    "summary",
    "recommendedAction",
    "guardrailStatus",
    "actionMode",
    "shouldEscalate",
    "actionReasons",
    "simulatedAction",
    "actionProcessedAt",
]


def log(level, message, **fields):
    print(json.dumps({"level": level, "message": message, **fields}))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_complaint_id(event):
    complaint_id = (event.get("pathParameters") or {}).get("complaintId", "")
    if not isinstance(complaint_id, str) or not complaint_id.strip():
        raise ValueError("'complaintId' path parameter is required")
    return complaint_id.strip()


def get_complaint_item(complaint_id):
    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(Key={"complaintId": complaint_id}, ConsistentRead=True)
    return response.get("Item")


def build_query_response(item):
    return {field: item[field] for field in RESPONSE_FIELDS if field in item}


def lambda_handler(event, _context):
    try:
        complaint_id = get_complaint_id(event)
        item = get_complaint_item(complaint_id)

        if not item:
            log("INFO", "Complaint query not found", complaintId=complaint_id)
            return response(404, {"error": "Complaint not found"})

        body = build_query_response(item)
        log(
            "INFO",
            "Complaint query succeeded",
            complaintId=complaint_id,
            processingStatus=body.get("processingStatus", ""),
        )
        return response(200, body)
    except ValueError as exc:
        log(
            "WARNING",
            "Complaint query validation failed",
            error=str(exc),
        )
        return response(400, {"error": str(exc)})
    except (ClientError, BotoCoreError) as exc:
        log(
            "ERROR",
            "Complaint query AWS dependency failure",
            errorType=type(exc).__name__,
            error=str(exc),
        )
        raise
