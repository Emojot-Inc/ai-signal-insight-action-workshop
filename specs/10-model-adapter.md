# Model Adapter Design

The analysis Lambda must use a thin model adapter.

Purpose:
- Hide Bedrock Converse request/response details from business logic.
- Normalize all model outputs into the internal analysis schema.
- Allow mock mode for demos and failure handling.

Required functions:
- analyze_message(message: str) -> dict
- analyze_with_bedrock_converse(message: str) -> dict
- analyze_with_mock(message: str) -> dict
- parse_model_json(text: str) -> dict
- validate_analysis_schema(data: dict) -> dict

Rules:
- Business logic must call analyze_message().
- Business logic must not directly call boto3 converse().
- Only the adapter may know Bedrock response structure.
- Do not implement OpenAI, Gemini, or other providers.
- Do not implement full multi-model switching.
- Keep Claude as the workshop model through Bedrock Converse.

Optional extension:
- A post-lab extension may change BEDROCK_MODEL_ID to another Bedrock Converse-compatible model.
- The extension must keep the same internal analysis schema and must not change ingest, event, query, or action contracts.
- Do not add adapter dispatch unless a new model requires different request fields, response extraction, prompt handling, or normalization.
