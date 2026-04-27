# Complaint ID Generation

`complaintId` must be generated only by `IngestFunction`.

Format:
- `cmp-<uuid-v4>`

Rules:
- Participants do not send `complaintId` in `POST /complaints`.
- `complaintId` will be provided by server-generated IDs.
- UUID generation must happen before any persistence or event emission.
- The complaint is not accepted unless the generated `complaintId` is used consistently in all downstream writes and publications.

The generated `complaintId` must be reused in:
- `POST /complaints` success response
- S3 object key
- EventBridge `ComplaintReceived` detail
- DynamoDB partition key
- `GET /complaints/{complaintId}` path lookup

Rationale:
- Prevent collisions across workshop participants.
- Teach system-owned identifiers for distributed workflows.
- Keep S3, EventBridge, and DynamoDB records aligned on one stable key.
