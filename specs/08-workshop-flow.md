# Workshop Flow

Target duration: 4 hours

Segments:
1. Framing and architecture
2. Ingest demo and hands-on requests
3. Complaint ID handoff and query-by-ID lookup
4. Analysis path and Bedrock output
5. Guardrails and compliance
6. Action routing
7. Failure handling and observability
8. Guided tuning / assessment
9. Platform engineering wrap-up

Participant interaction flow:
1. Submit a complaint to `POST /complaints`
2. Receive a server-generated `complaintId`
3. Use `GET /complaints/{complaintId}` to query the current status
4. Observe the complaint move from ingest to analysis to action
