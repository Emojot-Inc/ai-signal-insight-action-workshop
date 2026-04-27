Implement ingest_complaint Lambda.

Requirements:
- Parse Lambda proxy event body
- Validate channel and message
- Generate `complaintId` as `cmp-<uuid-v4>`
- Enrich payload with submittedAt UTC timestamp
- Store raw JSON in S3 under raw/YYYY/MM/DD/<complaintId>.json
- Create the initial DynamoDB complaint state item with `processingStatus=RECEIVED`
- Publish ComplaintReceived event to EventBridge
- Return 202 on success, 400 on validation failure
- Emit structured JSON logs

Do not call Bedrock from this function.
