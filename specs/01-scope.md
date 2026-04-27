# Scope

Build a simplified event-driven AI complaint processing system for a workshop.

In scope:
- HTTP API to accept complaint submissions
- HTTP API to query complaint status by generated complaint ID
- Raw complaint storage in S3
- Event emission to EventBridge
- Analysis Lambda using Amazon Bedrock
- Guardrails for harmful content and sensitive information
- Structured insights persisted to DynamoDB
- Action Lambda for escalation simulation
- CloudWatch structured logging
- Mock fallback mode for Bedrock failures

Out of scope:
- Frontend UI
- Authentication
- Real ticketing integrations
- Multi-tenant design
- Multi-region deployment
- Step Functions
- Container runtime
