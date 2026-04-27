# DynamoDB Data Model

Table: complaint-insights
Partition key: complaintId

This item is the read model for `GET /complaints/{complaintId}`.

Initial item created by ingest:
- complaintId
- submittedAt
- channel
- processingStatus
- rawS3Key

Attributes:
- complaintId
- submittedAt
- channel
- rawS3Key
- processingStatus
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
