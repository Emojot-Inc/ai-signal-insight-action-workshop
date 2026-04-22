# Instructor Guide

## Session Order (4 hours)

1. Framing and architecture
2. Ingest demo and hands-on requests
3. Analysis path and Bedrock output
4. Guardrails and compliance
5. Action routing
6. Failure handling and observability
7. Guided tuning and assessment
8. Platform engineering wrap-up

## Pre-Session Commands

Run once before participants join:

```bash
sam build
sam deploy --guided
```

Capture outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table
```

Set API URL for live calls:

```bash
API_URL=$(aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)
echo "$API_URL"
```

## Deterministic Demo Sequence

### Sequence 1: Normal Complaint

What to say: "First we run the happy path to establish baseline flow."

What to run:

```bash
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-001",
    "channel":"email",
    "message":"I was billed twice this month.",
    "customerName":"Taylor"
  }'
```

Expected output:

```json
{"status":"accepted","complaintId":"cmp-demo-001"}
```

What screen to show:

```bash
aws logs tail /aws/lambda/<stack-name>-ingest --since 5m --follow
aws logs tail /aws/lambda/<stack-name>-analyze --since 5m --follow
aws logs tail /aws/lambda/<stack-name>-action --since 5m --follow
```

Concept to explain: event-driven chaining (`ComplaintReceived` -> analyze -> `ComplaintAnalyzed` -> action).

### Sequence 2: Abusive Complaint

What to say: "Now we show guardrail intervention logic using mock mode."

What to run:

```bash
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-002",
    "channel":"chat",
    "message":"Your agent is stupid and I hate this service."
  }'
```

Expected output:

```json
{"status":"accepted","complaintId":"cmp-demo-002"}
```

What screen to show:

```bash
aws dynamodb get-item \
  --table-name <InsightsTableName-from-stack-output> \
  --key '{"complaintId":{"S":"cmp-demo-002"}}'
```

Concept to explain: `guardrailStatus` is persisted and can drive policy decisions.

### Sequence 3: PII-Heavy Complaint

What to say: "Same flow, but with sensitive-information risk."

What to run:

```bash
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-003",
    "channel":"web",
    "message":"My passport and national ID details were posted publicly."
  }'
```

Expected output:

```json
{"status":"accepted","complaintId":"cmp-demo-003"}
```

What screen to show: analyze log line containing `guardrailStatus` and emitted `ComplaintAnalyzed` detail including `piiDetected`.

Concept to explain: policy-aware enrichment before downstream action.

### Sequence 4: Invalid Complaint

What to say: "Validation should fail fast at ingest and avoid downstream noise."

What to run:

```bash
curl -s -i -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-004",
    "channel":"email"
  }'
```

Expected output:

```text
HTTP/1.1 400 Bad Request
...
{"error":"'message' is required and must be a non-empty string"}
```

What screen to show: ingest log with `level=WARNING` and validation error.

Concept to explain: boundary validation as the first reliability control.

## Failure Mode Walkthrough

Force Bedrock failure in deployed env:

```bash
aws lambda update-function-configuration \
  --function-name <stack-name>-analyze \
  --environment "Variables={INSIGHTS_TABLE_NAME=<table>,EVENTS_BUS_NAME=ai-workshop-bus,BEDROCK_MODEL_ID=placeholder-model-id,BEDROCK_GUARDRAIL_ID=placeholder-guardrail-id,BEDROCK_GUARDRAIL_VERSION=DRAFT,USE_MOCK_BEDROCK=true,FORCE_BEDROCK_FAILURE=true,MOCK_INVALID_MODEL_OUTPUT=false,PROMPT_FILE=prompt.txt}"
```

Invalid model-output simulation:

```bash
aws lambda update-function-configuration \
  --function-name <stack-name>-analyze \
  --environment "Variables={INSIGHTS_TABLE_NAME=<table>,EVENTS_BUS_NAME=ai-workshop-bus,BEDROCK_MODEL_ID=placeholder-model-id,BEDROCK_GUARDRAIL_ID=placeholder-guardrail-id,BEDROCK_GUARDRAIL_VERSION=DRAFT,USE_MOCK_BEDROCK=true,FORCE_BEDROCK_FAILURE=false,MOCK_INVALID_MODEL_OUTPUT=true,PROMPT_FILE=prompt.txt}"
```

Fallback note:
- If live AWS calls are slow, switch to local demo with:
```bash
sam build
sam local start-api
```
