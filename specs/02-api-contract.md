# API Contract

Endpoint:
POST /complaints

Request JSON:
- complaintId: string, required
- channel: string, required
- message: string, required
- customerName: string, optional
- customerEmail: string, optional

Success response:
HTTP 202
{
  "status": "accepted",
  "complaintId": "<value>"
}

Validation failure:
HTTP 400
{
  "error": "<message>"
}