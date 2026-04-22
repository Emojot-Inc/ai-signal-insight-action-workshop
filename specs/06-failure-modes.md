# Failure Modes

1. Validation failure at ingest
- Missing message
- HTTP 400
- Structured log

2. Bedrock failure
- Simulated by env flag or forced exception
- Analysis function must log error clearly

3. Invalid model output
- Parser/schema validation error
- Item must not be persisted as successful

4. Guardrail intervention
- Abusive or PII-heavy complaint
- Log and capture guardrailStatus