# Complaint Processing State Model

The DynamoDB complaint item is the read model for `GET /complaints/{complaintId}`.

Lifecycle states:
- `RECEIVED`
- `ANALYZED`
- `ACTIONED`
- `FAILED_ANALYSIS`
- `FAILED_ACTION`

State ownership:
- `IngestFunction` creates the initial item with `processingStatus=RECEIVED`
- `AnalyzeFunction` persists normalized insight fields and advances the item to `ANALYZED`
- `ActionFunction` persists simulated action fields and advances the item to `ACTIONED`
- `AnalyzeFunction` sets `FAILED_ANALYSIS` when processing fails after ingest acceptance
- `ActionFunction` sets `FAILED_ACTION` when simulated action persistence fails

Core item fields:
- complaintId
- submittedAt
- channel
- processingStatus
- rawS3Key

Analysis fields:
- sentiment
- urgency
- category
- piiDetected
- summary
- recommendedAction
- guardrailStatus

Action fields:
- actionMode
- shouldEscalate
- actionReasons
- simulatedAction
- actionProcessedAt

Rules:
- Query responses return the current DynamoDB item as the complaint snapshot.
- Partial records are valid and must be returned while the workflow is still in progress.
- Duplicate handling is a delivery idempotency concern for ingest, analyze, and action stages rather than a user-entered ID concern.
