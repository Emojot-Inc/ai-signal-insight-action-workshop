# API Contract

Endpoint 1:
POST /complaints

Request JSON:
- channel: string, required
- message: string, required
- customerName: string, optional
- customerEmail: string, optional

Success response:
HTTP 202
{
  "status": "accepted",
  "complaintId": "cmp-<uuid-v4>"
}

Validation failure:
HTTP 400
{
  "error": "<message>"
}

Endpoint 2:
GET /complaints/{complaintId}

Request:
- request body: none
- path parameter: complaintId

Success response:
HTTP 200
{
  "complaintId": "cmp-<uuid-v4>",
  "submittedAt": "<timestamp>",
  "channel": "<value>",
  "processingStatus": "<value>"
}

Optional response fields when available:
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

Not found:
HTTP 404
{
  "error": "Complaint not found"
}
