# Troubleshooting

## 1) `sam` Commands Fail

Symptom:
- `zsh: command not found: sam`

Fix:
1. Install AWS SAM CLI.
2. Verify:

```bash
sam --version
```

## 2) `sam validate` Shows Metadata Permission Warnings

Symptom:
- Warnings about writing `/Users/.../.aws-sam/metadata.json`

Impact:
- Template validation can still succeed.

Fix options:
1. Ignore in restricted environments.
2. Disable telemetry for current shell:

```bash
export SAM_CLI_TELEMETRY=0
sam validate
```

## 3) Ingest Returns `400`

Symptom:
- Response body:

```json
{"error":"'message' is required and must be a non-empty string"}
```

Checks:
1. Ensure request JSON contains `complaintId`, `channel`, `message`.
2. Ensure all three are non-empty strings.

Quick test:

```bash
curl -s -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{"complaintId":"cmp-test-1","channel":"email","message":"test"}'
```

## 4) Ingest Returns `500`

Symptom:
- Response body:

```json
{"error":"Failed to process complaint"}
```

Typical causes:
1. S3 write failure.
2. EventBridge `PutEvents` failure.

Debug:

```bash
aws logs tail /aws/lambda/<stack-name>-ingest --since 10m
```

Look for fields:
- `errorType`
- `error`
- `s3Bucket`
- `s3Key`

## 5) Analyze Fails Before Writing DynamoDB

Symptom:
- Analyze Lambda errors with parsing/validation messages.

Typical causes:
1. Invalid model JSON.
2. Schema mismatch (`sentiment`, `urgency`, `category`, word limits).

Debug:

```bash
aws logs tail /aws/lambda/<stack-name>-analyze --since 10m
```

Look for:
- `Analyze validation/parsing failure`

## 6) Bedrock Mode

Default in template:
- `USE_MOCK_BEDROCK=true`

This enables deterministic model output without live Bedrock dependency for
template-level defaults and local overrides.

The checked-in `samconfig.toml` deploys with live Bedrock by default:

```bash
sam build
sam deploy
```

Alternative profiles:

```bash
sam deploy --config-env mock
sam deploy --config-env dev
sam deploy --config-env failure
sam deploy --config-env invalid
```

CloudFormation creates the workshop guardrail and publishes a version for the
analyzer automatically. Bedrock model access still needs to be enabled in the
target AWS account and region.

If deploy fails during change set creation with
`AWS::EarlyValidation::PropertyValidation`, check the Bedrock guardrail
resource definition in `template.yaml`. A common cause is the guardrail `Name`
exceeding the Bedrock limit of 50 characters.

Failure simulation flags:
- `FORCE_BEDROCK_FAILURE=true` forces Bedrock failure path.
- `MOCK_INVALID_MODEL_OUTPUT=true` forces invalid model output path.

Deploy using the failure profile (example):

```bash
sam build
sam deploy --config-env failure
```

## 7) No Action Triggered

Symptom:
- Analyze succeeds, but action logs are missing.

Checks:
1. Event bus is `ai-workshop-bus`.
2. Analyze emits `detail-type` `ComplaintAnalyzed`.
3. Action rule is deployed and enabled.

Rule status check:

```bash
aws events describe-rule \
  --name <stack-name>-complaint-analyzed \
  --event-bus-name ai-workshop-bus
```

## 8) DynamoDB Item Not Found

Symptom:
- Complaint accepted but no item in insights table.

Checks:
1. Confirm analyze succeeded in logs.
2. Query exact `complaintId`:

```bash
aws dynamodb get-item \
  --table-name <InsightsTableName-from-stack-output> \
  --key '{"complaintId":{"S":"<complaint-id>"}}'
```

3. If missing, replay analyze locally:

```bash
sam local invoke AnalyzeFunction --event events/analyze-event.json
```
