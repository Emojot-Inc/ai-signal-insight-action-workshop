Implement query_complaint Lambda.

Requirements:
- Add GET /complaints/{complaintId}
- Read complaint state from DynamoDB using complaintId
- Return current complaint snapshot for partial and completed processing states
- Return 404 when complaintId is not found
- Emit structured JSON logs

Notes:
- DynamoDB is the source of truth for complaint lookup
- Do not call Bedrock from this function
- Do not read S3 for normal lookup requests
- Persist simulated action results so the query API can return full status
