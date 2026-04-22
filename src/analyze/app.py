import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError


SENTIMENT_VALUES = {"positive", "neutral", "negative"}
URGENCY_VALUES = {"low", "medium", "high"}
CATEGORY_VALUES = {"billing", "service", "delivery", "technical", "compliance", "other"}

s3_client = boto3.client("s3")
dynamodb_resource = boto3.resource("dynamodb")
events_client = boto3.client("events")
bedrock_client = boto3.client("bedrock-runtime")


def log(level, message, **fields):
    print(json.dumps({"level": level, "message": message, **fields}))


def read_prompt_template():
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    prompt_path = os.path.join(os.path.dirname(__file__), prompt_file)
    with open(prompt_path, "r", encoding="utf-8") as file_handle:
        return file_handle.read().strip()


def render_prompt(template, complaint):
    return template.format(
        complaint_id=complaint.get("complaintId", ""),
        channel=complaint.get("channel", ""),
        message=complaint.get("message", ""),
        customer_name=complaint.get("customerName", ""),
        customer_email=complaint.get("customerEmail", ""),
    )


def load_complaint_from_s3(bucket, key):
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def validate_complaint_payload(complaint):
    if not isinstance(complaint, dict):
        raise ValueError("Complaint payload in S3 must be a JSON object")
    for field in ["complaintId", "channel", "message"]:
        value = complaint.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Complaint payload field '{field}' is missing or invalid")


def infer_mock_guardrail_status(message):
    lowered = message.lower()
    harmful_markers = ["idiot", "stupid", "hate", "kill", "abuse"]
    pii_markers = ["ssn", "social security", "passport", "credit card", "national id", "email", "phone"]

    has_harmful = any(marker in lowered for marker in harmful_markers)
    has_pii = any(marker in lowered for marker in pii_markers)

    if has_harmful and has_pii:
        return "INTERVENED_HARMFUL_AND_PII"
    if has_harmful:
        return "INTERVENED_HARMFUL"
    if has_pii:
        return "INTERVENED_PII"
    return "CLEAR"


def build_mock_model_output(complaint):
    message = complaint.get("message", "")
    guardrail_status = infer_mock_guardrail_status(message)

    # These deterministic mock branches make workshop demos reproducible.
    if guardrail_status == "INTERVENED_HARMFUL":
        output = {
            "sentiment": "negative",
            "urgency": "high",
            "category": "compliance",
            "piiDetected": False,
            "summary": "Abusive complaint content detected and should be handled with care.",
            "recommendedAction": "Escalate for compliance review.",
        }
    elif guardrail_status in {"INTERVENED_PII", "INTERVENED_HARMFUL_AND_PII"}:
        output = {
            "sentiment": "negative",
            "urgency": "high",
            "category": "compliance",
            "piiDetected": True,
            "summary": "Sensitive personal data appears in the complaint message.",
            "recommendedAction": "Escalate and mask sensitive data.",
        }
    else:
        output = {
            "sentiment": "negative",
            "urgency": "medium",
            "category": "service",
            "piiDetected": False,
            "summary": "Customer reports a service issue and seeks quick resolution.",
            "recommendedAction": "Escalate to service support.",
        }

    if os.getenv("MOCK_INVALID_MODEL_OUTPUT", "false").lower() == "true":
        return "not-json-response", guardrail_status

    return json.dumps(output), guardrail_status


def invoke_model(prompt, complaint):
    if os.getenv("FORCE_BEDROCK_FAILURE", "false").lower() == "true":
        raise RuntimeError("Forced Bedrock failure for failure-mode demo")

    if os.getenv("USE_MOCK_BEDROCK", "false").lower() == "true":
        return build_mock_model_output(complaint)

    model_id = os.getenv("BEDROCK_MODEL_ID", "")
    guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID", "")
    guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION", "")

    request_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }

    invoke_kwargs = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
        "body": json.dumps(request_payload),
    }
    if guardrail_id:
        invoke_kwargs["guardrailIdentifier"] = guardrail_id
    if guardrail_version:
        invoke_kwargs["guardrailVersion"] = guardrail_version

    response = bedrock_client.invoke_model(**invoke_kwargs)
    response_body = json.loads(response["body"].read())
    content = response_body.get("content", [])
    if not content:
        raise ValueError("Bedrock response did not include content")

    guardrail_action = None
    headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
    if isinstance(headers, dict):
        guardrail_action = headers.get("x-amzn-bedrock-guardrail-action")
    if not guardrail_action:
        guardrail_action = response_body.get("amazon-bedrock-guardrailAction")

    if guardrail_action == "INTERVENED":
        guardrail_status = "INTERVENED"
    elif guardrail_id:
        guardrail_status = "APPLIED"
    else:
        guardrail_status = "NOT_CONFIGURED"

    return content[0].get("text", ""), guardrail_status


def extract_json_object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == "{":
            try:
                obj, _ = decoder.raw_decode(text[index:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError("Model output did not contain a valid JSON object")


def _validate_max_words(value, max_words, field_name):
    if len(value.split()) > max_words:
        raise ValueError(f"'{field_name}' must be at most {max_words} words")


def validate_model_output(output):
    if not isinstance(output, dict):
        raise ValueError("Model output must be a JSON object")

    sentiment = output.get("sentiment")
    urgency = output.get("urgency")
    category = output.get("category")
    pii_detected = output.get("piiDetected")
    summary = output.get("summary")
    recommended_action = output.get("recommendedAction")

    if sentiment not in SENTIMENT_VALUES:
        raise ValueError(f"'sentiment' must be one of: {sorted(SENTIMENT_VALUES)}")
    if urgency not in URGENCY_VALUES:
        raise ValueError(f"'urgency' must be one of: {sorted(URGENCY_VALUES)}")
    if category not in CATEGORY_VALUES:
        raise ValueError(f"'category' must be one of: {sorted(CATEGORY_VALUES)}")
    if not isinstance(pii_detected, bool):
        raise ValueError("'piiDetected' must be a boolean")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("'summary' must be a non-empty string")
    if not isinstance(recommended_action, str) or not recommended_action.strip():
        raise ValueError("'recommendedAction' must be a non-empty string")

    _validate_max_words(summary.strip(), 30, "summary")
    _validate_max_words(recommended_action.strip(), 20, "recommendedAction")

    return {
        "sentiment": sentiment,
        "urgency": urgency,
        "category": category,
        "piiDetected": pii_detected,
        "summary": summary.strip(),
        "recommendedAction": recommended_action.strip(),
    }


def write_insight_item(item):
    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    table.put_item(Item=item)


def emit_complaint_analyzed_event(detail):
    bus_name = os.getenv("EVENTS_BUS_NAME", "")
    response = events_client.put_events(
        Entries=[
            {
                "Source": "emojot.workshop.complaints",
                "DetailType": "ComplaintAnalyzed",
                "EventBusName": bus_name,
                "Detail": json.dumps(detail),
            }
        ]
    )
    entry = response.get("Entries", [{}])[0]
    if entry.get("ErrorCode"):
        raise RuntimeError(
            f"EventBridge put_events failed: {entry.get('ErrorCode')} {entry.get('ErrorMessage')}"
        )


def build_insight_item(complaint_id, submitted_at, complaint, validated, guardrail_status, s3_key):
    return {
        "complaintId": complaint_id,
        "submittedAt": submitted_at or complaint.get("submittedAt", ""),
        "channel": complaint.get("channel", ""),
        "sentiment": validated["sentiment"],
        "urgency": validated["urgency"],
        "category": validated["category"],
        "piiDetected": validated["piiDetected"],
        "summary": validated["summary"],
        "recommendedAction": validated["recommendedAction"],
        "guardrailStatus": guardrail_status,
        "processingStatus": "COMPLETED",
        "rawS3Key": s3_key,
    }


def lambda_handler(event, _context):
    detail = event.get("detail", {})
    complaint_id = detail.get("complaintId", "")
    s3_bucket = detail.get("s3Bucket", "")
    s3_key = detail.get("s3Key", "")
    submitted_at = detail.get("submittedAt", "")

    try:
        if not complaint_id or not s3_bucket or not s3_key:
            raise ValueError("Event detail must include complaintId, s3Bucket, and s3Key")

        log("INFO", "Analyze started", complaintId=complaint_id, s3Bucket=s3_bucket, s3Key=s3_key)

        complaint = load_complaint_from_s3(s3_bucket, s3_key)
        validate_complaint_payload(complaint)
        prompt_template = read_prompt_template()
        prompt = render_prompt(prompt_template, complaint)
        raw_model_output, guardrail_status = invoke_model(prompt, complaint)
        parsed_output = extract_json_object(raw_model_output)
        validated = validate_model_output(parsed_output)

        processed_at = datetime.now(timezone.utc).isoformat()
        item = build_insight_item(
            complaint_id=complaint_id,
            submitted_at=submitted_at,
            complaint=complaint,
            validated=validated,
            guardrail_status=guardrail_status,
            s3_key=s3_key,
        )
        write_insight_item(item)

        analyzed_event_detail = {
            "complaintId": complaint_id,
            "sentiment": validated["sentiment"],
            "urgency": validated["urgency"],
            "category": validated["category"],
            "piiDetected": validated["piiDetected"],
            "guardrailStatus": guardrail_status,
            "recommendedAction": validated["recommendedAction"],
            "processedAt": processed_at,
        }
        emit_complaint_analyzed_event(analyzed_event_detail)

        log(
            "INFO",
            "Analyze completed",
            complaintId=complaint_id,
            processingStatus=item["processingStatus"],
            guardrailStatus=guardrail_status,
            sentiment=item["sentiment"],
            urgency=item["urgency"],
        )

        return {"status": "ok", "complaintId": complaint_id, "processedAt": processed_at}
    except (ClientError, BotoCoreError) as exc:
        log(
            "ERROR",
            "Analyze AWS dependency failure",
            complaintId=complaint_id,
            errorType=type(exc).__name__,
            error=str(exc),
        )
        raise
    except ValueError as exc:
        log(
            "ERROR",
            "Analyze validation/parsing failure",
            complaintId=complaint_id,
            errorType=type(exc).__name__,
            error=str(exc),
        )
        raise
    except Exception as exc:
        log(
            "ERROR",
            "Analyze unexpected failure",
            complaintId=complaint_id,
            errorType=type(exc).__name__,
            error=str(exc),
        )
        raise
