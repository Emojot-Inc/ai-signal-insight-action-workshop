Implement analyze_complaint Lambda.

Requirements:
- Triggered by ComplaintReceived EventBridge event
- Read complaint JSON from S3
- Build model prompt from prompt.txt
- Invoke Bedrock or mock mode
- Parse only JSON output
- Validate output fields and enums
- Store normalized item in DynamoDB
- Emit ComplaintAnalyzed event to EventBridge
- Emit structured JSON logs

Do not implement downstream notification integrations.