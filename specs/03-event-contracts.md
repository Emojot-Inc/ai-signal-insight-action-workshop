# Event Contracts

Event bus:
ai-workshop-bus

Event 1:
source: emojot.workshop.complaints
detail-type: ComplaintReceived

detail:
- complaintId
- s3Bucket
- s3Key
- submittedAt

Event 2:
source: emojot.workshop.complaints
detail-type: ComplaintAnalyzed

detail:
- complaintId
- sentiment
- urgency
- category
- piiDetected
- guardrailStatus
- guardrailTracePresent
- recommendedAction
- processedAt
