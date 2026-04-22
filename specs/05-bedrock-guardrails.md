# Bedrock and Guardrails

Use Amazon Bedrock for complaint analysis.

Expected output JSON:
- sentiment: positive|neutral|negative
- urgency: low|medium|high
- category: billing|service|delivery|technical|compliance|other
- piiDetected: boolean
- summary: max 30 words
- recommendedAction: max 20 words

Guardrails intent:
- harmful/abusive content control
- sensitive information / PII control

Implementation requirements:
- analysis code must support both real Bedrock mode and USE_MOCK_BEDROCK=true mode
- model output must be parsed and schema-validated before persistence