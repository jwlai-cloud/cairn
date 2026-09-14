# Deploying the testing link

The rules require a working test link with free access through 2026-10-08. This is the
shortest path to one that does not need an IAM role.

## Run it in fixture mode

Fixture mode makes no AWS API calls at all, so the service needs **no instance role**.
That removes the only step requiring IAM admin, and removes any per-click model cost.

The real-model claim does not depend on the hosted link. The demo video shows
`mode bedrock · us.amazon.nova-lite-v1:0` in the header with the decision loop filling
over fifteen seconds of genuine inference, and `app/agents/smoke.py` reproduces it for
anyone with credentials. The hosted link's job is "does it work when I click it", and
fixture mode answers that identically every time - which is also what makes it
reproducible for a judge.

If you would rather the link ran Bedrock, see the last section. It needs an instance role
and it costs money per visitor.

## What the image already guarantees

Verified on the current build, not assumed:

    262MB          slim base, no build toolchain in the final layer
    uid 10001      non-root
    /healthz       returns credentialsRequired:false in fixture mode
    PID 1          uvicorn itself, via exec, so SIGTERM is delivered
    1s             observed graceful stop, not the runtime's kill timeout
    $PORT          honoured by both the command and the healthcheck

## Deploy

Needs `apprunner:*`, `ecr:*` and `iam:CreateServiceLinkedRole` on the account. The
`mimir-bedrock` user has none of these, so run this from an admin session.

    ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    REGION=us-east-1
    REPO=cairn

    aws ecr create-repository --repository-name "$REPO" --region "$REGION" || true
    aws ecr get-login-password --region "$REGION" \
      | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

    # App Runner is amd64 only; build for it explicitly on an Apple Silicon machine.
    docker buildx build --platform linux/amd64 \
      -t "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest" --push .

    aws apprunner create-service --region "$REGION" \
      --service-name cairn \
      --source-configuration "{
        \"ImageRepository\": {
          \"ImageIdentifier\": \"$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest\",
          \"ImageRepositoryType\": \"ECR\",
          \"ImageConfiguration\": {
            \"Port\": \"8080\",
            \"RuntimeEnvironmentVariables\": {\"CAIRN_MODE\": \"fixture\"}
          }
        },
        \"AutoDeploymentsEnabled\": false
      }" \
      --instance-configuration '{"Cpu": "0.25 vCPU", "Memory": "1 GB"}' \
      --health-check-configuration '{"Protocol":"HTTP","Path":"/healthz","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}'

Then read the URL back:

    aws apprunner list-services --region us-east-1 \
      --query "ServiceSummaryList[?ServiceName=='cairn'].ServiceUrl" --output text

Confirm it logged out, in a private window: the room loads, Inject all then Run analysis
produce three options, and Attempt interlock override is refused.

## Cost

App Runner bills provisioned memory continuously and vCPU only while a request is being
served.

    provisioned memory   1 GB x $0.007/GB-hour x 24h        = $0.168 / day
    active compute       0.25 vCPU x $0.064/vCPU-hour
                         at ~10 minutes of use a day        = $0.003 / day
                                                              -------------
                                                              ~$0.17 / day
                                                              ~$5.20 / month

Through to the 2026-10-08 access deadline, roughly **$5**. Judging traffic will not move
that meaningfully: the whole point of the memory line dominating is that idle costs the
same as busy at this size.

Pause it when the window closes rather than deleting it, so the URL survives:

    aws apprunner pause-service --region us-east-1 --service-arn <arn>

## If the link should run Bedrock instead

Two extra steps, and a real cost per visitor.

1. Create an instance role that App Runner can assume, and attach
   `docs/deploy/bedrock-access.json` to it. The service then reads credentials from
   instance metadata, so nothing is baked into the image - which
   `.github/scripts/assert-no-aws-credentials.sh` enforces in CI.
2. Set `CAIRN_MODE=bedrock` and `CAIRN_BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0`.

Measured cost per analysis: 30,253 input and 2,504 output tokens. Nova Lite's rate is not
published on its model card, so treat a bracket of $0.06-$0.30 per million input as the
range - somewhere between a fifth of a cent and a cent per click.

The thing to be careful about is not the unit cost but the absence of a limit. A public
URL is an unbounded number of clicks, each one a real model call. Before pointing the
hosted link at Bedrock, add a per-session cap that falls back to fixture mode when it is
hit, and keep the header naming whichever provider actually ran - the badge already does
that correctly.
