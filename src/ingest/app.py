import base64
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError


s3_client = boto3.client("s3")
events_client = boto3.client("events")


def log(level, message, **fields):
    entry = {"level": level, "message": message, **fields}
    print(json.dumps(entry))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        raise ValueError("Request body is required")

    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except Exception as exc:
            raise ValueError("Request body is not valid base64-encoded UTF-8 JSON") from exc

    if isinstance(raw_body, dict):
        return raw_body

    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON object")

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Request body is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object")

    return parsed


def validate(payload):
    required_fields = ["complaintId", "channel", "message"]
    for field in required_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"'{field}' is required and must be a non-empty string")


def store_raw_record(bucket_name, s3_key, raw_record):
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(raw_record).encode("utf-8"),
        ContentType="application/json",
    )


def publish_received_event(events_bus_name, event_detail):
    put_events_response = events_client.put_events(
        Entries=[
            {
                "Source": "emojot.workshop.complaints",
                "DetailType": "ComplaintReceived",
                "EventBusName": events_bus_name,
                "Detail": json.dumps(event_detail),
            }
        ]
    )

    entry_result = put_events_response.get("Entries", [{}])[0]
    if entry_result.get("ErrorCode"):
        raise RuntimeError(
            f"EventBridge put_events failed: {entry_result.get('ErrorCode')} {entry_result.get('ErrorMessage')}"
        )


def lambda_handler(event, _context):
    raw_bucket_name = os.getenv("RAW_BUCKET_NAME", "")
    events_bus_name = os.getenv("EVENTS_BUS_NAME", "")

    try:
        payload = parse_body(event)
        validate(payload)
    except ValueError as exc:
        log(
            "WARNING",
            "Complaint validation failed",
            error=str(exc),
            requestId=event.get("requestContext", {}).get("requestId"),
        )
        return response(400, {"error": str(exc)})

    submitted_at = datetime.now(timezone.utc).isoformat()
    complaint_id = payload["complaintId"]
    timestamp = datetime.now(timezone.utc)
    s3_key = f"raw/{timestamp:%Y/%m/%d}/{complaint_id}.json"

    raw_record = {**payload, "submittedAt": submitted_at}

    try:
        store_raw_record(raw_bucket_name, s3_key, raw_record)
        log(
            "INFO",
            "Stored complaint in S3",
            complaintId=complaint_id,
            s3Bucket=raw_bucket_name,
            s3Key=s3_key,
        )

        event_detail = {
            "complaintId": complaint_id,
            "s3Bucket": raw_bucket_name,
            "s3Key": s3_key,
            "submittedAt": submitted_at,
        }
        publish_received_event(events_bus_name, event_detail)
        log(
            "INFO",
            "Published ComplaintReceived event",
            complaintId=complaint_id,
            eventBusName=events_bus_name,
        )
    except (ClientError, BotoCoreError, RuntimeError) as exc:
        log(
            "ERROR",
            "Ingest processing failed",
            complaintId=complaint_id,
            s3Bucket=raw_bucket_name,
            s3Key=s3_key,
            errorType=type(exc).__name__,
            error=str(exc),
        )
        return response(500, {"error": "Failed to process complaint"})

    return response(202, {"status": "accepted", "complaintId": complaint_id})
