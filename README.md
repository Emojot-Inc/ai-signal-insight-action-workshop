# AI Signal Insight Action Workshop

AWS SAM starter for a simplified event-driven complaint workflow:
API ingest -> S3/EventBridge -> analysis -> DynamoDB -> action simulation.

## Prerequisites

- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed
- Python 3.12

## Repository Structure

```text
.
├── template.yaml
├── src/
│   ├── ingest/app.py
│   ├── analyze/app.py
│   └── action/app.py
└── events/
    ├── ingest-api.json
    ├── ingest-api-sensitive.json
    ├── analyze-event.json
    └── action-event.json
```

## Local Commands

Build:

```bash
sam build
```

Run local API:

```bash
sam local start-api
```

In a second terminal, call the local endpoint:

```bash
curl -X POST http://127.0.0.1:3000/complaints \
  -H "Content-Type: application/json" \
  -d '{"customerId":"CUST-001","channel":"email","message":"I was charged twice."}'
```

Invoke functions directly with sample events:

```bash
sam local invoke IngestFunction --event events/ingest-api.json
sam local invoke IngestFunction --event events/ingest-api-sensitive.json
sam local invoke AnalyzeFunction --event events/analyze-event.json
sam local invoke ActionFunction --event events/action-event.json
```

## Deploy Commands

First deployment (guided):

```bash
sam deploy --guided
```

Subsequent deployments:

```bash
sam build
sam deploy
```
