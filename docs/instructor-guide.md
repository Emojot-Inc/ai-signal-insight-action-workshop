# Instructor Guide

This guide is the runbook for facilitators leading the workshop.

## Session Outcomes

By the end of the session, participants should understand:

- how the API, EventBridge, S3, DynamoDB, and Lambda pieces connect
- why the workflow is split into ingest, analyze, and action stages
- how mock AI output differs from live Bedrock analysis
- how guardrails and validation affect downstream behavior

## Recommended Delivery Mode

Use one of these two approaches:

- `mock` profile for repeatable demos and hands-on labs
- `default` profile for a live Bedrock walkthrough after the basics are stable

If time is tight, run most of the session in mock mode and reserve live Bedrock for a short compare-and-contrast demo.

## Pre-Session Checklist

Run these before participants join:

```bash
sam build
sam deploy --config-env mock
```

If you plan to show live Bedrock as well:

```bash
sam build
sam deploy
```

Also verify:

- Docker is running if you will show `sam local`
- the target AWS account can access Bedrock in `us-east-1`
- Claude Haiku 4.5 access is enabled in Bedrock for the target account
- you know the deployed stack name you plan to use on screen

## Capture Useful Outputs

List outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table
```

Set a working API URL:

```bash
API_BASE_URL="<your-api-base-url>"
POST_API_URL="$API_BASE_URL/complaints"
echo "$API_BASE_URL"
```

Keep these handy as well:

- `ApiBaseUrl`
- `ApiUrl`
- `RawComplaintsBucketName`
- `InsightsTableName`
- `ComplaintEventsBusName`
- `BedrockGuardrailId`
- `BedrockGuardrailVersion`

## Suggested Session Order

1. explain the architecture and responsibilities of each function
2. show the happy path end to end
3. show harmful content and PII examples
4. compare mock-mode behavior with live guardrail behavior
5. inspect logs and query complaint status by ID
6. show one failure-mode deployment profile
7. wrap with cost, cleanup, and extension ideas

## Demo Sequence

### Sequence 1: Normal Service Issue

What to say:
"First we run the happy path so everyone sees the baseline event flow."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"email",
    "message":"Your support team ignored my issue for three days and I still cannot access my account."
  }'
```

Expected result:

```json
{"status":"accepted","complaintId":"cmp-<uuid-v4>"}
```

What to show:

```bash
aws logs tail /aws/lambda/<stack-name>-ingest --since 5m --follow
aws logs tail /aws/lambda/<stack-name>-analyze --since 5m --follow
aws logs tail /aws/lambda/<stack-name>-action --since 5m --follow
```

Key teaching point:
`ComplaintReceived` leads to analysis, then `ComplaintAnalyzed` leads to action.
The participant receives a generated ID and uses it to query the complaint later.

### Sequence 2: Harmful Content

What to say:
"Now we send content that should trigger the harmful-content path while still keeping the workflow observable."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"chat",
    "message":"I hate your agent. I will kill you."
  }'
```

What to show:

```bash
curl -s "$API_BASE_URL/complaints/<complaintId>"
```

Key teaching point:
`guardrailStatus` is persisted and becomes policy input for downstream actioning.

### Sequence 3: Harmful Content Plus PII

What to say:
"This one combines abuse with sensitive personal-document references."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"Your idiot staff leaked my passport number and national ID. I will kill him."
  }'
```

What to show:

- the analyze log line with `guardrailStatus`
- the query response with `piiDetected=true`

Key teaching point:
guardrail-aware normalization can still produce structured output for downstream systems.

### Sequence 4: PII-Heavy Complaint

What to say:
"This complaint is sensitive without being overtly threatening."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"My passport number and credit card details were visible in the complaint thread."
  }'
```

What to show:

- analyze log output
- `piiDetected=true`
- `category=compliance`

Key teaching point:
PII handling is not the same thing as harmful-language detection.

### Sequence 5: Sensitive But Still Analyzable

What to say:
"Not every risky complaint is blocked. Some are still analyzed and routed normally."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"My personal identification documents were exposed on your website and other users could view them."
  }'
```

What to show:

- the item with `guardrailStatus=APPLIED` in live mode
- the recommended action

Key teaching point:
guardrails can annotate and moderate without always halting the business workflow.

### Sequence 6: Boundary-Crossing Message With PII

What to say:
"This example is softer in tone but still creates a compliance workflow because it includes personal contact details."

What to run:

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"web",
    "message":"I really like one of your support agents, please ask her to call me at 202-555-0147."
  }'
```

What to show:

- `piiDetected=true`
- the normalized recommendation
- the action-stage decision reasons

Key teaching point:
the workflow is about operational signal extraction, not just negative sentiment.

### Sequence 7: Invalid Complaint

What to say:
"Validation should fail at the front door and avoid downstream noise."

What to run:

```bash
curl -s -i -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"email"
  }'
```

Expected result:

```text
HTTP/1.1 400 Bad Request
...
{"error":"'message' is required and must be a non-empty string"}
```

Key teaching point:
ingest validation protects downstream systems from malformed requests.

## Failure-Mode Demos

Use these when you want to show controlled failure paths:

```bash
sam build
sam deploy --config-env failure
sam deploy --config-env invalid
```

What each profile demonstrates:

- `failure`: forced runtime failure before Bedrock output is produced
- `invalid`: invalid AI output that fails JSON/schema validation

Comparison table:

| Scenario | Where it fails | API response | S3 raw complaint | DynamoDB insight | EventBridge downstream | Action stage | What you would see |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Invalid request | Ingest validation | `400 Bad Request` | No | No | No `ComplaintReceived` event | No | Clear validation error returned to caller |
| Ingest infrastructure failure | Ingest after validation | `500 Failed to process complaint` | Maybe | Maybe partial `RECEIVED` item if failure happens after initial write | No downstream progress if store or publish fails | No | Ingest logs show `Ingest processing failed` with `errorType` |
| Forced analyzer failure | Analyze runtime | `202 Accepted` already returned | Yes | Item remains queryable, typically with `FAILED_ANALYSIS` | `ComplaintReceived` exists, `ComplaintAnalyzed` does not | No | Analyze logs show an unexpected failure |
| Invalid AI output | Analyze validation/parsing | `202 Accepted` already returned | Yes | Item remains queryable, typically with `FAILED_ANALYSIS` | `ComplaintReceived` exists, `ComplaintAnalyzed` does not | No | Analyze logs show validation or parsing failure |
| Guardrail intervention | Analyze, but recovered | `202 Accepted` already returned | Yes | Yes | Both events emitted | Yes | Insight is saved with guardrail metadata |

Suggested framing:

- show that the analyzer logs structured failure details
- show that invalid output does not get silently persisted
- connect this back to production hardening and observability

## Instructor Tips

- copy the `complaintId` from the POST response and reuse it in lookup examples
- keep one terminal dedicated to log tails and one for `curl`
- if live Bedrock adds latency, call that out explicitly so participants do not think the app is stuck
- if a live Bedrock demo is flaky, switch back to `mock` and keep momentum

## Wrap-Up Points

- the infrastructure is intentionally simple so participants can reason about it quickly
- the analyzer validates AI output before trusting it
- the model adapter is a natural extension point for showing how another model can reuse the same analysis contract
- the action stage is simulated on purpose and is a natural extension point
- most workshop cost comes from Bedrock, not the surrounding serverless components

## Optional Model Swap Note

If the group asks how to try another Bedrock Converse-compatible model, explain that the analyzer already passes `BEDROCK_MODEL_ID` into the shared Converse request. For this workshop, changing the `BedrockModelId` deploy parameter is enough as long as the model supports the same Converse request and response shape and can follow the same JSON-only prompt.

## Supporting Docs

- participant flow: [participant-guide.md](participant-guide.md)
- common issues: [troubleshooting.md](troubleshooting.md)
- cost and cleanup: [costing.md](costing.md)
