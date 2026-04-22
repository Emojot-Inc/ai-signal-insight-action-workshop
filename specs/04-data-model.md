# DynamoDB Data Model

Table: complaint-insights
Partition key: complaintId

Attributes:
- complaintId
- submittedAt
- channel
- sentiment
- urgency
- category
- piiDetected
- summary
- recommendedAction
- guardrailStatus
- processingStatus
- rawS3Key