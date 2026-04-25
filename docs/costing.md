# Workshop Costing Guide

This guide gives workshop users a practical way to think about cost before deploying the stack.

## Short Version

For normal workshop usage, the serverless infrastructure is inexpensive.

The main cost driver is Amazon Bedrock:

- model input and output tokens
- Bedrock Guardrails usage in live mode

If you want one simple number to communicate to participants, use:

- plan for a few dollars per workshop run
- use **about $5 per deployment** as a safe workshop budget placeholder

That is intentionally a rule-of-thumb number, not a billing guarantee.

## What Is in Scope

The stack in [template.yaml](/Users/ravindu-emojot/Documents/emojot/code/ai-signal-insight-action-workshop/template.yaml) includes:

- API Gateway
- three Lambda functions
- one S3 bucket
- one DynamoDB on-demand table
- one EventBridge custom bus plus rules
- optional live Amazon Bedrock analysis
- optional Bedrock Guardrails
- CloudWatch Logs and X-Ray

## Cost Pattern by Mode

### Mock Mode

If you deploy with `sam deploy --config-env mock` or `dev`:

- there is no live Bedrock inference cost
- there is no live Bedrock Guardrails usage cost
- most cost comes from API Gateway, Lambda, DynamoDB, S3, and logs
- for normal workshop traffic, this is usually very small

Mock mode is the safest option if you want repeatable demos with minimal spend.

### Live Bedrock Mode

If you deploy with the default profile:

- infrastructure cost is still usually small
- Bedrock inference becomes the dominant cost
- guardrail usage adds a smaller but real extra cost

For this repo, live mode is where nearly all meaningful spend happens.

## A Useful Mental Model

At workshop scale:

- API Gateway, Lambda, EventBridge, S3, and DynamoDB are usually tiny costs
- idle resources are close to zero except for stored data and retained logs
- Bedrock cost grows almost linearly with the number of complaint analyses

That means your budget is mostly a question of:

- how many complaints participants submit
- how long the complaint messages are
- whether live Bedrock is enabled

## Rough Workshop Example

A reasonable workshop scenario might look like:

- 25 participants
- 10 to 20 complaint submissions each
- roughly 250 to 500 total complaint submissions

For that range:

- mock mode is typically near-zero to very low cost
- live mode is still usually only a few dollars, with Bedrock dominating

If you need a single planning number, assume:

- **250 submissions**: low single-digit dollars in live mode
- **500 submissions**: still typically only a few dollars in live mode

## What Usually Stays Small

For most workshop users, these are not the parts to worry about:

- Lambda request charges
- Lambda compute charges
- EventBridge events
- DynamoDB request charges
- S3 request and storage charges for the small workshop payloads
- X-Ray at workshop scale

CloudWatch Logs can become the main lingering small cost if you leave the stack around and retain logs for a long time.

## How to Keep Costs Down

- use `mock` mode for most of the workshop
- switch to live Bedrock only for one short comparison demo
- keep complaint payloads short and realistic
- delete the stack when the session ends
- avoid leaving workshop data and logs around indefinitely

## Pricing Verification

AWS pricing changes over time, so treat any workshop estimate as illustrative.

Before a customer-facing session or a large class, verify the current pricing pages for:

- AWS Lambda
- Amazon API Gateway
- Amazon EventBridge
- Amazon DynamoDB
- Amazon S3
- Amazon Bedrock
- Amazon Bedrock Guardrails
- Amazon CloudWatch Logs
- AWS X-Ray

## Cleanup

When the workshop is over, delete the stack to stop ongoing cost:

```bash
sam delete --stack-name ai-signal-insight-action-workshop
```

If you used the `dev` profile:

```bash
sam delete --stack-name ai-signal-insight-action-workshop-dev
```

## If Stack Deletion Is Blocked

If the raw complaints bucket still contains objects, empty it first:

```bash
aws s3 rm s3://<RawComplaintsBucketName-from-stack-output> --recursive
```

Then retry stack deletion:

```bash
sam delete --stack-name ai-signal-insight-action-workshop
```

## Cleanup Checklist

- delete the CloudFormation stack
- empty the raw-complaints bucket if deletion is blocked
- remove DynamoDB workshop data if you want a clean rerun
- remove log groups if you want logs gone immediately

## Final Recommendation

If someone asks, "Is this safe to run for a workshop?" the practical answer is:

- yes, especially in mock mode
- live mode is still modest, but Bedrock is the part to watch
- budgeting **about $5 per workshop deployment** is a reasonable conservative planning number
