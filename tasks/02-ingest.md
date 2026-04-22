Implement ingest_complaint Lambda.

Requirements:
- Parse Lambda proxy event body
- Validate complaintId, channel, message
- Enrich payload with submittedAt UTC timestamp
- Store raw JSON in S3 under raw/YYYY/MM/DD/<complaintId>.json
- Publish ComplaintReceived event to EventBridge
- Return 202 on success, 400 on validation failure
- Emit structured JSON logs

Do not call Bedrock from this function.