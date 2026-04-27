# Task: Implement Analysis Lambda with Bedrock Converse

Implement analyze_complaint Lambda.

Trigger:
- EventBridge event with detail-type ComplaintReceived

Responsibilities:
1. Read complaint from S3 using s3Bucket and s3Key from the event.
2. Extract complaint message.
3. Call analyze_message(message).
4. Update the existing DynamoDB complaint item with normalized analysis fields and `processingStatus=ANALYZED`.
5. Publish ComplaintAnalyzed event to EventBridge.
6. Emit structured JSON logs.

Model adapter:
- Use Bedrock Converse API through boto3 bedrock-runtime.
- Use Claude via Bedrock as the selected model.
- Support mock mode using USE_MOCK_BEDROCK=true.
- Keep provider-specific code isolated inside adapter functions.

Validation:
- Model output must be JSON.
- Validate required fields and enum values.
- If output is invalid, log failure and do not write a successful analyzed state.

Do not:
- Use InvokeModel directly.
- Add multiple model providers.
- Add Step Functions.
- Add SNS/email/Jira/Slack.
- Add frontend UI.
