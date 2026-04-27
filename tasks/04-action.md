Implement trigger_action Lambda.

Requirements:
- Triggered by ComplaintAnalyzed EventBridge event
- Evaluate escalation rules:
  - urgency == high
  - OR sentiment == negative and category == compliance
  - OR piiDetected == true and urgency != low
- Persist simulated action fields to the DynamoDB complaint item and set `processingStatus=ACTIONED`
- Log action result as structured JSON
- Return successfully without external side effects

Keep action logic configurable and readable.
