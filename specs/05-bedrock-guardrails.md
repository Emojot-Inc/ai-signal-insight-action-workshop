# Bedrock Converse and Guardrails

The analysis Lambda must use Amazon Bedrock Runtime Converse API for model invocation.

Selected workshop model:
- Claude via Amazon Bedrock

Important:
- The workshop uses Claude as the selected model for simplicity.
- The system must not leak Claude-specific response formatting outside the model adapter.
- The application owns the internal output contract.

Environment variables:
- USE_MOCK_BEDROCK=true|false
- BEDROCK_MODEL_ID=<model-id>
- BEDROCK_GUARDRAIL_ID=<guardrail-id>
- BEDROCK_GUARDRAIL_VERSION=<guardrail-version>
- BEDROCK_REGION=<aws-region>

Internal output schema:
{
  "sentiment": "positive|neutral|negative",
  "urgency": "low|medium|high",
  "category": "billing|service|delivery|technical|compliance|other",
  "piiDetected": true|false,
  "summary": "string, max 30 words",
  "recommendedAction": "string, max 20 words"
}

Converse requirements:
- Use boto3 bedrock-runtime client.
- Use client.converse().
- Use messages with role=user.
- Use system prompt for output rules.
- Use inferenceConfig with maxTokens and temperature.
- Use guardrailConfig when guardrail env vars are provided.
- Extract text from response["output"]["message"]["content"].
- Parse only valid JSON from the model response.
- Validate all fields before updating the DynamoDB complaint item with analyzed fields.

Guardrails intent:
- Content filtering for harmful/abusive language
- Sensitive information / PII handling
- Capture guardrail trace/status where available

Fallback:
- If USE_MOCK_BEDROCK=true, do not call Bedrock.
- Return deterministic mock analysis based on complaint message keywords.
