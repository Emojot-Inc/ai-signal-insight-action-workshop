# Troubleshooting

This guide covers the most common issues workshop users run into when running locally or in AWS.

## 1. `sam` command not found

Symptom:

```text
zsh: command not found: sam
```

What it means:

- AWS SAM CLI is not installed or is not on your shell path

Fix:

```bash
sam --version
```

If that still fails, install or reinstall the SAM CLI and open a new shell.

## 2. Docker is not running for local commands

Symptom:

- `sam local start-api` or `sam local invoke` fails before the Lambda container starts

What it means:

- Docker is required for local SAM execution

Fix:

```bash
docker --version
```

Then start Docker Desktop or your local Docker runtime and try again.

## 3. `sam build` or `sam local start-api` fails unexpectedly

Quick checks:

```bash
python3 --version
sam --version
docker --version
```

Also confirm you are in the repo root that contains `template.yaml`.

## 4. `sam validate` shows metadata permission warnings

Symptom:

- warnings about writing `.aws-sam/metadata.json`

Impact:

- template validation can still succeed in restricted environments

Optional workaround:

```bash
export SAM_CLI_TELEMETRY=0
sam validate
```

## 5. `POST /complaints` returns `400`

Typical response:

```json
{"error":"'message' is required and must be a non-empty string"}
```

Checks:

- request body must be a JSON object
- `channel` must be a non-empty string
- `message` must be a non-empty string

Known-good test:

```bash
curl -s -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{"channel":"email","message":"test"}'
```

## 6. `POST /complaints` returns `500`

Typical response:

```json
{"error":"Failed to process complaint"}
```

Likely causes:

- S3 write failure
- initial DynamoDB state write failure
- EventBridge `PutEvents` failure
- missing AWS permissions in a deployed environment

Debug with ingest logs:

```bash
aws logs tail /aws/lambda/<stack-name>-ingest --since 10m
```

Look for fields such as:

- `errorType`
- `error`
- `s3Bucket`
- `s3Key`

## 7. Analyze fails before updating DynamoDB analysis fields

Likely causes:

- invalid or incomplete event detail
- invalid AI output
- schema mismatch in `sentiment`, `urgency`, `category`, `summary`, or `recommendedAction`
- forced failure profile enabled

Debug:

```bash
aws logs tail /aws/lambda/<stack-name>-analyze --since 10m
```

Look for:

- `Analyze validation/parsing failure`
- `Analyze AWS dependency failure`
- `Analyze unexpected failure`

## 8. Bedrock live mode does not work

Checks:

- confirm you deployed with `UseMockBedrock="false"` or used the default profile
- confirm Bedrock model access is enabled in the same AWS account and region
- confirm the region matches the configured deployment region
- confirm the stack outputs include a guardrail ID and guardrail version for live mode

Helpful commands:

```bash
sam deploy
aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table
```

Notes:

- local template defaults use mock mode
- the checked-in default deploy profile uses live Bedrock in `us-east-1`
- the stack creates the workshop guardrail automatically for live deployments

## 9. Sample `sam local invoke` events do not behave as expected

Use the event files in `events/` that match the current handlers:

- `events/ingest-api.json` for `IngestFunction`
- `events/ingest-api-sensitive.json` for `IngestFunction`
- `events/analyze-event.json` for `AnalyzeFunction`
- `events/action-event.json` for `ActionFunction`
- `events/query-api.json` for `QueryFunction`

Remember:

- direct invoke tests one function only
- it does not automatically trigger the full EventBridge chain

## 10. No action log appears after analysis

Checks:

- confirm analyze completed successfully
- confirm the event bus is `ai-workshop-bus`
- confirm analyze emitted `ComplaintAnalyzed`
- confirm the EventBridge rule is enabled

Rule status check:

```bash
aws events describe-rule \
  --name <stack-name>-complaint-analyzed \
  --event-bus-name ai-workshop-bus
```

## 11. `GET /complaints/{complaintId}` returns `404`

Checks:

- confirm you copied the exact `complaintId` returned by the POST response
- confirm ingest succeeded in logs
- confirm you are calling the correct API base URL and path

Example:

```bash
curl -s "<your-api-base-url>/complaints/<complaintId>"
```

## 12. Query response only shows partial status

This is expected while the asynchronous workflow is still in progress.

What it means:

- `RECEIVED` means ingest accepted the complaint and stored the initial record
- `ANALYZED` means analysis completed but action has not finished
- `ACTIONED` means the simulated action outcome has been persisted

Checks:

- tail ingest, analyze, and action logs
- retry the lookup after a short delay

## 13. DynamoDB item is missing

Checks:

- confirm ingest succeeded in logs
- if you expected analysis fields, confirm analyze succeeded in logs
- query the exact `complaintId`
- make sure you are checking the correct table name from stack outputs

Example:

```bash
aws dynamodb get-item \
  --table-name <InsightsTableName-from-stack-output> \
  --key '{"complaintId":{"S":"<complaint-id>"}}'
```

## 14. Stack deletion fails because the S3 bucket is not empty

CloudFormation cannot delete a non-empty bucket.

Empty the bucket first:

```bash
aws s3 rm s3://<RawComplaintsBucketName-from-stack-output> --recursive
```

Then delete the stack:

```bash
sam delete --stack-name ai-signal-insight-action-workshop
```

## 15. You need a faster fallback during the workshop

If live Bedrock is slowing the session down or failing unexpectedly, switch back to deterministic mock mode:

```bash
sam build
sam deploy --config-env mock
```
