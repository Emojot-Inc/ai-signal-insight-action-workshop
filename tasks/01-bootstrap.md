Create the initial project structure for an AWS SAM serverless application.

Requirements:
- Python runtime
- template.yaml with placeholders for API Gateway, 3 Lambda functions, S3 bucket, DynamoDB table, EventBridge bus and rules
- src/ingest/app.py
- src/analyze/app.py
- src/action/app.py
- events/ with 4 sample payload files
- README with local setup and deploy steps

Do not implement business logic yet.
Keep code minimal and runnable.