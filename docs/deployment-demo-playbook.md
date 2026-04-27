# Deployment Demo Playbook

This playbook is for the deployed AWS workshop flow only. It does not include local fallback commands.

Assumption: run these commands from the repository root.

## 0. Pre-Session Checks

```bash
aws sts get-caller-identity
sam --version
python3 --version
```

## 1. Build And Deploy Live Bedrock Stack

```bash
sam validate
sam build
sam deploy
```

This deploys the main live Bedrock profile from `samconfig.toml`.

## 2. Capture Stack Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table
```

Set API variables:

```bash
API_BASE_URL=$(aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text)

POST_API_URL="$API_BASE_URL/complaints"

echo "$API_BASE_URL"
echo "$POST_API_URL"
```

## 3. Start Log Tails

Use separate terminals.

Ingest logs:

```bash
aws logs tail /aws/lambda/ai-signal-insight-action-workshop-ingest \
  --since 10m \
  --follow
```

Analyze logs:

```bash
aws logs tail /aws/lambda/ai-signal-insight-action-workshop-analyze \
  --since 10m \
  --follow
```

Action logs:

```bash
aws logs tail /aws/lambda/ai-signal-insight-action-workshop-action \
  --since 10m \
  --follow
```

Query logs:

```bash
aws logs tail /aws/lambda/ai-signal-insight-action-workshop-query \
  --since 10m \
  --follow
```

## 4. Main Demo: Create Complaint And Poll State

This command block shows:

```text
RECEIVED -> ANALYZED -> ACTIONED
```

```bash
echo "Submitting complaint..."

RESPONSE=$(curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "message": "Your support team ignored my issue for three days and I still cannot access my account."
  }')

echo
echo "POST response:"
echo "$RESPONSE" | jq

COMPLAINT_ID=$(echo "$RESPONSE" | jq -r '.complaintId')

echo
echo "Complaint ID: $COMPLAINT_ID"
echo
echo "Polling complaint state..."

LAST_STATUS=""

for i in {1..80}; do
  RESULT=$(curl -s "$API_BASE_URL/complaints/$COMPLAINT_ID")
  STATUS=$(echo "$RESULT" | jq -r '.processingStatus // "UNKNOWN"')

  if [ "$STATUS" != "$LAST_STATUS" ]; then
    echo
    echo "---- $(date +%H:%M:%S) | status changed: $STATUS ----"
    echo "$RESULT" | jq
    LAST_STATUS="$STATUS"
  fi

  if [ "$STATUS" = "ACTIONED" ] || [ "$STATUS" = "FAILED_ANALYSIS" ] || [ "$STATUS" = "FAILED_ACTION" ]; then
    echo
    echo "Final state reached: $STATUS"
    break
  fi

  sleep 0.25
done
```

## 5. Scenario: Billing Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "message": "I was charged twice for my monthly subscription and I need a refund immediately."
  }' | jq
```

## 6. Scenario: Delivery Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "message": "My package is late and the delivery tracking has not been updated for two days."
  }' | jq
```

## 7. Scenario: Technical Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "chat",
    "message": "The mobile app keeps crashing whenever I try to upload a document."
  }' | jq
```

## 8. Scenario: Abusive Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "chat",
    "message": "I hate your support agent. Your team are useless idiots."
  }' | jq
```

## 9. Scenario: Strong Harmful Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "chat",
    "message": "I hate your agent. I will kill you."
  }' | jq
```

## 10. Scenario: PII / Compliance Complaint

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "message": "My passport number and credit card details were visible in the complaint thread."
  }' | jq
```

## 11. Scenario: Harmful Content Plus PII

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "message": "Your idiot staff leaked my passport number and national ID. I will kill him."
  }' | jq
```

## 12. Scenario: Boundary-Crossing Message With Phone Number

```bash
curl -s -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "message": "I really like one of your support agents, please ask her to call me at 202-555-0147."
  }' | jq
```

## 13. Reusable Submit-And-Poll Function

Run this once:

```bash
submit_and_poll () {
  MESSAGE="$1"
  CHANNEL="${2:-web}"

  RESPONSE=$(curl -s -X POST "$POST_API_URL" \
    -H "Content-Type: application/json" \
    -d "{
      \"channel\": \"$CHANNEL\",
      \"message\": \"$MESSAGE\"
    }")

  echo
  echo "POST response:"
  echo "$RESPONSE" | jq

  COMPLAINT_ID=$(echo "$RESPONSE" | jq -r '.complaintId')

  echo
  echo "Polling complaint: $COMPLAINT_ID"

  LAST_STATUS=""

  for i in {1..80}; do
    RESULT=$(curl -s "$API_BASE_URL/complaints/$COMPLAINT_ID")
    STATUS=$(echo "$RESULT" | jq -r '.processingStatus // "UNKNOWN"')

    if [ "$STATUS" != "$LAST_STATUS" ]; then
      echo
      echo "---- $(date +%H:%M:%S) | status changed: $STATUS ----"
      echo "$RESULT" | jq
      LAST_STATUS="$STATUS"
    fi

    if [ "$STATUS" = "ACTIONED" ] || [ "$STATUS" = "FAILED_ANALYSIS" ] || [ "$STATUS" = "FAILED_ACTION" ]; then
      echo
      echo "Final state reached: $STATUS"
      break
    fi

    sleep 0.25
  done
}
```

Then use it like this:

```bash
submit_and_poll "My passport number and credit card details were visible in the complaint thread." "web"
```

```bash
submit_and_poll "I was charged twice for my monthly subscription and I need a refund immediately." "email"
```

```bash
submit_and_poll "The mobile app keeps crashing whenever I try to upload a document." "chat"
```

## 14. Invalid Input Demo: Missing Message

```bash
curl -s -i -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email"
  }'
```

Teaching point:

```text
This fails before the system accepts responsibility.
```

## 15. Invalid Input Demo: Empty Message

```bash
curl -s -i -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "message": ""
  }'
```

## 16. Invalid Input Demo: Client Sends complaintId

```bash
curl -s -i -X POST "$POST_API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "complaintId": "cmp-manual-id",
    "channel": "email",
    "message": "I want to submit this complaint with my own ID."
  }'
```

## 17. Failure Demo: Analyzer Runtime Failure

Deploy failure mode:

```bash
sam build
sam deploy --config-env failure
```

Submit and poll:

```bash
submit_and_poll "Your support team ignored my issue for three days and I still cannot access my account." "email"
```

Teaching point:

```text
The API returned 202, but async analysis failed later.
```

Restore live Bedrock:

```bash
sam build
sam deploy
```

## 18. Failure Demo: Invalid Model Output

Deploy invalid-output mode:

```bash
sam build
sam deploy --config-env invalid
```

Submit and poll:

```bash
submit_and_poll "My package is late and the delivery tracking has not been updated for two days." "web"
```

Teaching point:

```text
The system refuses to persist malformed model output as a valid insight.
```

Restore live Bedrock:

```bash
sam build
sam deploy
```

## 19. Inspect DynamoDB Item Directly

Get table name:

```bash
INSIGHTS_TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[?OutputKey=='InsightsTableName'].OutputValue" \
  --output text)

echo "$INSIGHTS_TABLE_NAME"
```

Fetch item:

```bash
aws dynamodb get-item \
  --table-name "$INSIGHTS_TABLE_NAME" \
  --key "{\"complaintId\":{\"S\":\"$COMPLAINT_ID\"}}" \
  --output json
```

## 20. Inspect Raw S3 Object

Get bucket:

```bash
RAW_BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name ai-signal-insight-action-workshop \
  --query "Stacks[0].Outputs[?OutputKey=='RawComplaintsBucketName'].OutputValue" \
  --output text)

echo "$RAW_BUCKET_NAME"
```

List recent raw records:

```bash
aws s3 ls "s3://$RAW_BUCKET_NAME/raw/" --recursive
```

Copy one object key from the output, then:

```bash
aws s3 cp "s3://$RAW_BUCKET_NAME/<raw-object-key>" -
```

## 21. Cleanup After Workshop

```bash
sam delete --stack-name ai-signal-insight-action-workshop
```

If the bucket is not empty:

```bash
aws s3 rm "s3://$RAW_BUCKET_NAME" --recursive
sam delete --stack-name ai-signal-insight-action-workshop
```
