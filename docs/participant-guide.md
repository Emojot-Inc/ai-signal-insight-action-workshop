# Participant Guide

This guide is for workshop participants using the repo during the session.

## What You Are Building

The workshop flow is:

1. submit a complaint to `POST /complaints`
2. receive a server-generated `complaintId`
3. store the raw complaint in S3
4. analyze the complaint and normalize the result
5. update the complaint state in DynamoDB
6. simulate a downstream action decision
7. query the complaint later with `GET /complaints/{complaintId}`

## Before You Start

Make sure these work:

```bash
sam --version
docker --version
aws sts get-caller-identity
```

If you are running locally, start from the repo root:

```bash
sam build
sam local start-api
```

Keep `sam local start-api` running in one terminal and use a second terminal for requests.

## Pick Your API URL

For local runs:

```bash
API_BASE_URL="http://127.0.0.1:3000"
POST_API_URL="$API_BASE_URL/complaints"
```

For deployed runs:

```bash
API_BASE_URL="<your-api-base-url>"
POST_API_URL="$API_BASE_URL/complaints"
```

## Demo Requests

### 1. Normal Service Issue

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"email",
    "message":"Your support team ignored my issue for three days and I still cannot access my account."
  }'
```

Expected response:

```json
{"status":"accepted","complaintId":"cmp-<uuid-v4>"}
```

Save the returned `complaintId` from the response and use it in the query examples below.

What to expect:

- `guardrailStatus` should be `CLEAR` in mock mode
- `category` should usually be `service`
- `urgency` should usually be `medium`

### 2. Harmful Content

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"chat",
    "message":"I hate your agent. I will kill you."
  }'
```

What to expect:

- mock mode may produce `INTERVENED_HARMFUL`
- live Bedrock with guardrails may produce `INTERVENED`
- `category` should be `compliance`
- `urgency` should be `high`

### 3. Harmful Content Plus PII

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"Your idiot staff leaked my passport number and national ID. I will kill him."
  }'
```

What to expect:

- mock mode should produce `INTERVENED_HARMFUL_AND_PII`
- `piiDetected` should be `true`
- `category` should be `compliance`
- `urgency` should be `high`

### 4. PII-Heavy Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"My passport number and credit card details were visible in the complaint thread."
  }'
```

What to expect:

- mock mode should produce `INTERVENED_PII`
- `piiDetected` should be `true`
- `category` should be `compliance`
- `urgency` should be `high`

### 5. Sensitive But Still Analyzable

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"My personal identification documents were exposed on your website and other users could view them."
  }'
```

What to expect:

- live Bedrock may return `guardrailStatus=APPLIED`
- `piiDetected` should be `true`
- `category` should be `compliance`
- the complaint can still be normalized and routed

### 6. Boundary-Crossing Message With Phone Number

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"I really like one of your support agents, please ask her to call me at 202-555-0147."
  }'
```

What to expect:

- live Bedrock may return `guardrailStatus=APPLIED`
- `piiDetected` should be `true`
- `category` should usually be `compliance`

### 7. Invalid Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web"
  }'
```

Expected response:

```json
{"error":"'message' is required and must be a non-empty string"}
```

## How to Inspect Results

For a deployed stack, first capture the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table
```

### Tail Logs

```bash
aws logs tail /aws/lambda/<stack-name>-ingest --since 10m --follow
aws logs tail /aws/lambda/<stack-name>-analyze --since 10m --follow
aws logs tail /aws/lambda/<stack-name>-action --since 10m --follow
```

### Query the Complaint

For local runs:

```bash
curl -s "http://127.0.0.1:3000/complaints/<complaintId>"
```

For deployed runs:

```bash
curl -s "$API_BASE_URL/complaints/<complaintId>"
```

Example response while the workflow is still in progress:

```json
{
  "complaintId": "cmp-<uuid-v4>",
  "submittedAt": "<timestamp>",
  "channel": "email",
  "processingStatus": "RECEIVED"
}
```

Example response after analysis and action finish:

```json
{
  "complaintId": "cmp-<uuid-v4>",
  "submittedAt": "<timestamp>",
  "channel": "email",
  "processingStatus": "ACTIONED",
  "sentiment": "negative",
  "urgency": "medium",
  "category": "service",
  "piiDetected": false,
  "summary": "Customer reports a service issue and seeks quick resolution.",
  "recommendedAction": "Escalate to service support.",
  "guardrailStatus": "CLEAR",
  "actionMode": "simulate",
  "shouldEscalate": false,
  "actionReasons": [],
  "simulatedAction": "no_escalation",
  "actionProcessedAt": "<timestamp>"
}
```

Look for fields such as:

- `complaintId`
- `submittedAt`
- `channel`
- `sentiment`
- `urgency`
- `category`
- `piiDetected`
- `guardrailStatus`
- `recommendedAction`
- `processingStatus`
- `simulatedAction`
- `shouldEscalate`

## Direct Function Tests

Use these when you want to invoke one function in isolation:

```bash
sam local invoke IngestFunction --event events/ingest-api.json
sam local invoke IngestFunction --event events/ingest-api-sensitive.json
sam local invoke AnalyzeFunction --event events/analyze-event.json
sam local invoke ActionFunction --event events/action-event.json
sam local invoke QueryFunction --event events/query-api.json
```

Notes:

- direct invocation does not reproduce the full end-to-end chain unless you trigger each step yourself
- the sample event files in `events/` are aligned to the current handlers in this repo

## What to Observe During the Workshop

- invalid input fails fast at ingest with a `400`
- successful ingest returns `202 Accepted`
- successful ingest returns a generated `complaintId`
- query results may show `RECEIVED`, `ANALYZED`, or `ACTIONED` depending on how far the asynchronous workflow has progressed
- the analyzer validates the AI response before persisting it
- the analyzer calls a model adapter, which keeps model-specific request and response handling away from the workflow logic
- the action stage is simulated and does not call external case-management systems

## Optional Model Swap

For another Bedrock Converse-compatible model, you do not need a separate adapter in this workshop. Change the deployed `BedrockModelId` parameter, keep the same prompt and schema validation, and compare the normalized output.

## If Something Breaks

Use [troubleshooting.md](docs/troubleshooting.md) for the most common workshop issues.
