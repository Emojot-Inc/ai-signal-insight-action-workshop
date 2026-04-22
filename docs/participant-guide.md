# Participant Guide

## Architecture (2 minutes)

Flow used in this workshop:

1. `POST /complaints` sends complaint JSON to `IngestFunction`.
2. Ingest validates payload, writes raw JSON to S3, emits `ComplaintReceived` on `ai-workshop-bus`.
3. `AnalyzeFunction` reads S3, runs Bedrock (or mock), validates model JSON, writes normalized record to DynamoDB, emits `ComplaintAnalyzed`.
4. `ActionFunction` evaluates escalation rules and logs a simulated action.

## Local Setup

Run these commands in the repo root:

```bash
sam build
sam local start-api
```

Keep `sam local start-api` running in terminal 1. Use terminal 2 for requests.

## Send Complaints

Normal complaint:

```bash
curl -s -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-1001",
    "channel":"email",
    "message":"I was charged twice for April.",
    "customerName":"Alex",
    "customerEmail":"alex@example.com"
  }'
```

Expected response:

```json
{"status":"accepted","complaintId":"cmp-1001"}
```

PII-heavy complaint:

```bash
curl -s -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-1002",
    "channel":"chat",
    "message":"My national ID and passport details were shared in the ticket.",
    "customerName":"Sam"
  }'
```

Invalid complaint (missing `message`):

```bash
curl -s -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId":"cmp-1003",
    "channel":"web"
  }'
```

Expected response:

```json
{"error":"'message' is required and must be a non-empty string"}
```

## Postman Equivalent

- Method: `POST`
- URL: `http://127.0.0.1:3000/complaints`
- Header: `Content-Type: application/json`
- Body type: `raw` + `JSON`
- Use the same JSON payloads shown above.

## What To Observe

1. Validation behavior: invalid input returns `400` immediately.
2. Structured logs: each Lambda prints JSON logs with `level`, `message`, and identifiers like `complaintId`.
3. Guardrail status: analyze stores `guardrailStatus` and includes it in analyzed event detail.
4. Simulated action only: action Lambda returns decision details without external integrations.

## Optional Direct Function Invocations

```bash
sam local invoke IngestFunction --event events/ingest-api.json
sam local invoke AnalyzeFunction --event events/analyze-event.json
sam local invoke ActionFunction --event events/action-event.json
```
