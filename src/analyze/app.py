import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError


SENTIMENT_VALUES = {"positive", "neutral", "negative"}
URGENCY_VALUES = {"low", "medium", "high"}
CATEGORY_VALUES = {"billing", "service", "delivery", "technical", "compliance", "other"}
DEFAULT_BEDROCK_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_SYSTEM_PROMPT = """You are an analyst for customer complaints.
Return only one valid JSON object with these exact fields:
- sentiment: one of positive, neutral, negative
- urgency: one of low, medium, high
- category: one of billing, service, delivery, technical, compliance, other
- piiDetected: boolean
- summary: concise summary, maximum 30 words
- recommendedAction: concise action, maximum 20 words"""

s3_client = boto3.client("s3")
dynamodb_resource = boto3.resource("dynamodb")
events_client = boto3.client("events")
_bedrock_runtime_client = None
_bedrock_runtime_region = None


def log(level, message, **fields):
    print(json.dumps({"level": level, "message": message, **fields}, default=str))


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_system_prompt():
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    prompt_path = os.path.join(os.path.dirname(__file__), prompt_file)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as file_handle:
            prompt = file_handle.read().strip()
            if prompt:
                return prompt
    return DEFAULT_SYSTEM_PROMPT


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


def analyze_message(message: str) -> dict:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Complaint message must be a non-empty string")

    if _env_flag("FORCE_BEDROCK_FAILURE"):
        raise RuntimeError("Forced Bedrock failure for failure-mode demo")

    if _env_flag("USE_MOCK_BEDROCK"):
        return analyze_with_mock(message.strip())

    return analyze_with_bedrock_converse(message.strip())


def analyze_with_mock(message: str) -> dict:
    guardrail_status = infer_mock_guardrail_status(message)
    model_output = build_mock_model_output(message, guardrail_status)
    if _env_flag("MOCK_INVALID_MODEL_OUTPUT"):
        model_output = "not-json-response"

    parsed_output = parse_model_json(model_output)
    validated = validate_analysis_schema(parsed_output)
    log(
        "INFO",
        "Mock analysis completed",
        modelProvider="mock",
        guardrailStatus=guardrail_status,
        guardrailTracePresent=False,
    )
    return {
        **validated,
        "guardrailStatus": guardrail_status,
        "guardrailTracePresent": False,
    }


def analyze_with_bedrock_converse(message: str) -> dict:
    model_id = get_bedrock_model_id()
    system_prompt = read_system_prompt()
    converse_request = build_converse_request(model_id, system_prompt, message)
    guardrail_configured = "guardrailConfig" in converse_request

    log(
        "INFO",
        "Calling Bedrock Converse",
        modelProvider="bedrock",
        modelId=model_id,
        guardrailConfigured=guardrail_configured,
    )

    response = get_bedrock_runtime_client().converse(**converse_request)
    metadata = extract_guardrail_metadata(response, guardrail_configured)

    log(
        "INFO",
        "Bedrock Converse response received",
        modelProvider="bedrock",
        modelId=model_id,
        stopReason=metadata.get("bedrockStopReason"),
        guardrailStatus=metadata["guardrailStatus"],
        guardrailTracePresent=metadata["guardrailTracePresent"],
        latencyMs=response.get("metrics", {}).get("latencyMs"),
        inputTokens=response.get("usage", {}).get("inputTokens"),
        outputTokens=response.get("usage", {}).get("outputTokens"),
    )

    response_text = extract_converse_text(response)
    parsed_output = parse_model_json(response_text)
    validated = validate_analysis_schema(parsed_output)
    return {**validated, **metadata}


def get_bedrock_runtime_client():
    global _bedrock_runtime_client, _bedrock_runtime_region

    region = os.getenv("BEDROCK_REGION", "").strip() or None
    if _bedrock_runtime_client is None or _bedrock_runtime_region != region:
        if region:
            _bedrock_runtime_client = boto3.client("bedrock-runtime", region_name=region)
        else:
            _bedrock_runtime_client = boto3.client("bedrock-runtime")
        _bedrock_runtime_region = region

    return _bedrock_runtime_client


def get_bedrock_model_id():
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID).strip()
    if not model_id:
        raise ValueError("BEDROCK_MODEL_ID is required when USE_MOCK_BEDROCK is false")
    return model_id


def build_converse_request(model_id, system_prompt, message):
    request = {
        "modelId": model_id,
        "system": [{"text": system_prompt}],
        "messages": [
            {
                "role": "user",
                "content": [{"text": message}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": 300,
            "temperature": 0.0,
        },
    }

    guardrail_config = build_guardrail_config()
    if guardrail_config:
        request["guardrailConfig"] = guardrail_config

    return request


def build_guardrail_config():
    guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID", "").strip()
    guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION", "").strip()

    if guardrail_id and guardrail_version:
        return {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
            "trace": "enabled",
        }

    if guardrail_id or guardrail_version:
        log(
            "WARNING",
            "Bedrock guardrail configuration is incomplete",
            hasGuardrailId=bool(guardrail_id),
            hasGuardrailVersion=bool(guardrail_version),
        )

    return None


def extract_converse_text(response):
    try:
        content = response["output"]["message"]["content"]
    except KeyError as exc:
        raise ValueError("Bedrock Converse response did not include output.message.content") from exc

    if not isinstance(content, list):
        raise ValueError("Bedrock Converse response content must be a list")

    text_parts = [
        block["text"]
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ]
    if not text_parts:
        raise ValueError("Bedrock Converse response did not include text content")

    return "".join(text_parts).strip()


def extract_guardrail_metadata(response, guardrail_configured):
    stop_reason = response.get("stopReason", "")
    trace_present = isinstance(response.get("trace"), dict) and bool(response.get("trace"))

    if stop_reason == "guardrail_intervened":
        guardrail_status = "INTERVENED"
    elif guardrail_configured:
        guardrail_status = "APPLIED"
    else:
        guardrail_status = "NOT_CONFIGURED"

    metadata = {
        "guardrailStatus": guardrail_status,
        "guardrailTracePresent": trace_present,
    }
    if stop_reason:
        metadata["bedrockStopReason"] = stop_reason
    return metadata


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


def build_mock_model_output(message, guardrail_status):
    lowered = message.lower()

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
    elif "refund" in lowered or "charged" in lowered or "invoice" in lowered:
        output = {
            "sentiment": "negative",
            "urgency": "medium",
            "category": "billing",
            "piiDetected": False,
            "summary": "Customer reports a billing issue and wants a quick resolution.",
            "recommendedAction": "Route to billing support.",
        }
    elif "late" in lowered or "delivery" in lowered or "package" in lowered:
        output = {
            "sentiment": "negative",
            "urgency": "medium",
            "category": "delivery",
            "piiDetected": False,
            "summary": "Customer reports a delivery issue requiring follow-up.",
            "recommendedAction": "Check shipment status.",
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

    return json.dumps(output)


def parse_model_json(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Model output must be a non-empty JSON string")

    candidates = [text.strip()]
    fenced = _strip_json_code_fence(text.strip())
    if fenced != candidates[0]:
        candidates.append(fenced)

    embedded = _extract_first_json_object(text)
    if embedded:
        candidates.append(embedded)

    last_error = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue

        if not isinstance(parsed, dict):
            raise ValueError("Model output JSON must be an object")
        return parsed

    raise ValueError("Model output must contain one valid JSON object") from last_error


def _strip_json_code_fence(text):
    if not text.startswith("```") or not text.endswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 3:
        return text

    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        return text

    return "\n".join(lines[1:-1]).strip()


def _extract_first_json_object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue

        try:
            _, end_index = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue

        return text[index : index + end_index]

    return None


def _validate_max_words(value, max_words, field_name):
    if len(value.split()) > max_words:
        raise ValueError(f"'{field_name}' must be at most {max_words} words")


def _normalize_enum_value(output, field_name, allowed_values):
    value = output.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field_name}' must be a non-empty string")

    normalized = value.strip().lower()
    if normalized not in allowed_values:
        raise ValueError(f"'{field_name}' must be one of: {sorted(allowed_values)}")
    return normalized


def validate_analysis_schema(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object")

    sentiment = _normalize_enum_value(data, "sentiment", SENTIMENT_VALUES)
    urgency = _normalize_enum_value(data, "urgency", URGENCY_VALUES)
    category = _normalize_enum_value(data, "category", CATEGORY_VALUES)
    pii_detected = data.get("piiDetected")
    summary = data.get("summary")
    recommended_action = data.get("recommendedAction")

    if not isinstance(pii_detected, bool):
        raise ValueError("'piiDetected' must be a boolean")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("'summary' must be a non-empty string")
    if not isinstance(recommended_action, str) or not recommended_action.strip():
        raise ValueError("'recommendedAction' must be a non-empty string")

    summary = summary.strip()
    recommended_action = recommended_action.strip()
    _validate_max_words(summary, 30, "summary")
    _validate_max_words(recommended_action, 20, "recommendedAction")

    return {
        "sentiment": sentiment,
        "urgency": urgency,
        "category": category,
        "piiDetected": pii_detected,
        "summary": summary,
        "recommendedAction": recommended_action,
    }


def write_insight_item(item):
    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    table.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(complaintId)",
    )


def get_existing_insight_item(complaint_id):
    table_name = os.getenv("INSIGHTS_TABLE_NAME", "")
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(Key={"complaintId": complaint_id}, ConsistentRead=True)
    return response.get("Item")


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


def build_insight_item(complaint_id, submitted_at, complaint, analysis, s3_key):
    item = {
        "complaintId": complaint_id,
        "submittedAt": submitted_at or complaint.get("submittedAt", ""),
        "channel": complaint.get("channel", ""),
        "sentiment": analysis["sentiment"],
        "urgency": analysis["urgency"],
        "category": analysis["category"],
        "piiDetected": analysis["piiDetected"],
        "summary": analysis["summary"],
        "recommendedAction": analysis["recommendedAction"],
        "guardrailStatus": analysis.get("guardrailStatus", "UNKNOWN"),
        "guardrailTracePresent": bool(analysis.get("guardrailTracePresent", False)),
        "processingStatus": "COMPLETED",
        "rawS3Key": s3_key,
    }
    if analysis.get("bedrockStopReason"):
        item["bedrockStopReason"] = analysis["bedrockStopReason"]
    return item


def build_complaint_analyzed_detail(complaint_id, analysis, processed_at):
    detail = {
        "complaintId": complaint_id,
        "sentiment": analysis["sentiment"],
        "urgency": analysis["urgency"],
        "category": analysis["category"],
        "piiDetected": analysis["piiDetected"],
        "guardrailStatus": analysis.get("guardrailStatus", "UNKNOWN"),
        "guardrailTracePresent": bool(analysis.get("guardrailTracePresent", False)),
        "recommendedAction": analysis["recommendedAction"],
        "processedAt": processed_at,
    }
    if analysis.get("bedrockStopReason"):
        detail["bedrockStopReason"] = analysis["bedrockStopReason"]
    return detail


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

        existing_item = get_existing_insight_item(complaint_id)
        if existing_item and existing_item.get("processingStatus") == "COMPLETED":
            log(
                "INFO",
                "Analyze skipped duplicate completed complaint",
                complaintId=complaint_id,
                rawS3Key=existing_item.get("rawS3Key", ""),
            )
            return {
                "status": "duplicate",
                "complaintId": complaint_id,
                "processedAt": existing_item.get("submittedAt", ""),
            }

        analysis = analyze_message(complaint["message"])

        processed_at = datetime.now(timezone.utc).isoformat()
        item = build_insight_item(
            complaint_id=complaint_id,
            submitted_at=submitted_at,
            complaint=complaint,
            analysis=analysis,
            s3_key=s3_key,
        )
        try:
            write_insight_item(item)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

            log(
                "INFO",
                "Analyze skipped duplicate write after retry race",
                complaintId=complaint_id,
                rawS3Key=s3_key,
            )
            return {
                "status": "duplicate",
                "complaintId": complaint_id,
                "processedAt": processed_at,
            }

        analyzed_event_detail = build_complaint_analyzed_detail(
            complaint_id=complaint_id,
            analysis=analysis,
            processed_at=processed_at,
        )
        emit_complaint_analyzed_event(analyzed_event_detail)

        log(
            "INFO",
            "Analyze completed",
            complaintId=complaint_id,
            processingStatus=item["processingStatus"],
            guardrailStatus=item["guardrailStatus"],
            guardrailTracePresent=item["guardrailTracePresent"],
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
