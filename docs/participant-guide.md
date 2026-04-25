# Participant Guide

This guide is for workshop participants using the repo during the session.

## What You Are Building

The workshop flow is:

1. submit a complaint to `POST /complaints`
2. store the raw complaint in S3
3. analyze the complaint and normalize the result
4. write the insight to DynamoDB
5. simulate a downstream action decision

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
API_URL="http://127.0.0.1:3000/complaints"
```

For deployed runs:

```bash
API_URL="<your-api-endpoint>"
```

## Demo Requests

### 1. Normal Service Issue

```bash
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-101",
    "channel":"email",
    "message":"Your support team ignored my issue for three days and I still cannot access my account."
  }'
```

Expected response:

```json
{"status":"accepted","complaintId":"cmp-demo-101"}
```

What to expect:

- `guardrailStatus` should be `CLEAR` in mock mode
- `category` should usually be `service`
- `urgency` should usually be `medium`

### 2. Harmful Content

```bash
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-102",
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
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-103",
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
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-104",
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
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-105",
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
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-106",
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
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-demo-199",
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

### Look Up the Insight Record

```bash
aws dynamodb get-item \
  --table-name <InsightsTableName-from-stack-output> \
  --key '{"complaintId":{"S":"cmp-demo-101"}}'
```

Look for fields such as:

- `sentiment`
- `urgency`
- `category`
- `piiDetected`
- `guardrailStatus`
- `recommendedAction`
- `processingStatus`

## Direct Function Tests

Use these when you want to invoke one function in isolation:

```bash
sam local invoke IngestFunction --event events/ingest-api.json
sam local invoke IngestFunction --event events/ingest-api-sensitive.json
sam local invoke AnalyzeFunction --event events/analyze-event.json
sam local invoke ActionFunction --event events/action-event.json
```

Notes:

- direct invocation does not reproduce the full end-to-end chain unless you trigger each step yourself
- the sample event files in `events/` are aligned to the current handlers in this repo

## What to Observe During the Workshop

- invalid input fails fast at ingest with a `400`
- successful ingest returns `202 Accepted`
- the analyzer validates the AI response before persisting it
- duplicate `complaintId` values will be skipped after a successful completed write
- the action stage is simulated and does not call external case-management systems

## If Something Breaks

Use [troubleshooting.md](/Users/ravindu-emojot/Documents/emojot/code/ai-signal-insight-action-workshop/docs/troubleshooting.md) for the most common workshop issues.
