# Complaint Query API

Endpoint:
GET /complaints/{complaintId}

Request:
- Request body: none
- Path parameter: `complaintId`

Source of truth:
- Read the current complaint snapshot from DynamoDB.
- Do not expose the raw complaint `message` by default.

Success response:
HTTP 200

Required fields:
- complaintId
- submittedAt
- channel
- processingStatus

Optional fields when available:
- sentiment
- urgency
- category
- piiDetected
- summary
- recommendedAction
- guardrailStatus
- actionMode
- shouldEscalate
- actionReasons
- simulatedAction
- actionProcessedAt

Behavior:
- If ingest succeeded and analysis or action is still running, return the partial item with the current `processingStatus`.
- If analysis has completed, include analysis and guardrail fields when present.
- If action has completed, include persisted simulated action fields when present.

Not found:
HTTP 404
{
  "error": "Complaint not found"
}
