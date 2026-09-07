# Enabling Bedrock for CAIRN

Fixture mode needs none of this. It is the CI gate and the reproducible replay, and it
runs with no credentials at all. This is only for the mode that puts a real model behind
the graph, which is what the demo and the hosted link should run.

## What is actually blocking

Not model enablement. The IAM user has no Bedrock permission whatsoever:

    User: arn:aws:iam::034355008385:user/mimir-bedrock is not authorized to perform:
    bedrock:InvokeModel on resource: .../inference-profile/us.amazon.nova-lite-v1:0
    because no identity-based policy allows the bedrock:InvokeModel action

The same error comes back for every model, which is the tell: a model that exists but is
not enabled denies on the *model*; an identity with no policy denies on the *action*.

## Two things to do, in an account with admin

**1. Attach the policy.** `bedrock-access.json` in this directory. It grants both actions,
because Strands calls `ConverseStream` and a policy with only `InvokeModel` fails at the
first token with an error that looks nothing like a permissions problem.

    aws iam put-user-policy --user-name mimir-bedrock \
      --policy-name cairn-bedrock-invoke \
      --policy-document file://docs/deploy/bedrock-access.json

A cross-region inference profile needs both ARNs: the profile itself, and the foundation
models in every region the profile can route to. Granting only the profile denies at the
routed region, which reads as a model problem and is not one.

**2. Enable the models.** Bedrock console, us-east-1, Model access. Request access for
Anthropic Claude Sonnet 5, Claude Haiku 4.5, and Amazon Nova Lite. Nova Lite is the
smoke-test model: cheap enough to exercise on every deploy.

## Confirming it

    for m in us.anthropic.claude-sonnet-5 \
             us.anthropic.claude-haiku-4-5-20251001-v1:0 \
             us.amazon.nova-lite-v1:0; do
      printf '%-46s ' "$m"
      aws bedrock-runtime converse --model-id "$m" --region us-east-1 \
        --messages '[{"role":"user","content":[{"text":"ping"}]}]' \
        --inference-config '{"maxTokens":8}' >/dev/null 2>&1 && echo ok || echo denied
    done

`AccessDeniedException` after this means the model is not enabled. `ValidationException`
means the model id is wrong, not the permission.

## On App Runner

Do not carry these keys into the image. App Runner takes an instance role; attach the
same policy to that role and the container gets credentials from the instance metadata
with nothing in the build. The CI check in `.github/scripts/assert-no-aws-credentials.sh`
exists to keep that true.
