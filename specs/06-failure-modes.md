# Failure Modes

1. Validation failure at ingest
- Missing message
- HTTP 400
- Structured log

2. Bedrock failure
- Simulated by env flag or forced exception
- Analysis function must log error clearly
- Complaint lookup may continue to return `RECEIVED` until failure state is persisted

3. Invalid model output
- Parser/schema validation error
- Item must not be persisted as successful
- Complaint lookup should not report a completed analysis state

4. Guardrail intervention
- Abusive or PII-heavy complaint
- Log and capture guardrailStatus

5. Complaint not found in query API
- `GET /complaints/{complaintId}` for an unknown ID
- HTTP 404
- Clear error response

6. Partial processing during query
- Ingest accepted but analyze or action has not finished
- HTTP 200 with the current partial complaint item
- `processingStatus` indicates whether the complaint is `RECEIVED`, `ANALYZED`, or `ACTIONED`
