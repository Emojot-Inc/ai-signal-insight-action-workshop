Add support for guardrail-aware analysis and failure-path handling.

Requirements:
- Capture and persist guardrailStatus
- Add mock cases for abusive and PII-heavy messages
- Add clear structured logging for each failure mode
- Do not silently swallow exceptions