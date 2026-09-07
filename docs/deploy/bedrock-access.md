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

**1. Extend the user's existing inline policy** with `bedrock-access.json` from this
directory. It is a superset: the Titan embedding model the other project on this user
already had is kept exactly, and `amazon.nova-*` covers the Nova Micro entry it replaces.

Adding a second inline policy was rejected. All inline policies on one principal share a
2048 non-whitespace character budget, and although the visible policy is only 247
characters, others exist. Replacing the one policy sidesteps the budget question.

For App Runner, put the same document in a customer-managed policy and attach it to the
instance role instead:

    aws iam create-policy --policy-name cairn-bedrock-invoke \
      --policy-document file://docs/deploy/bedrock-access.json

The document grants both actions, because Strands calls `ConverseStream` and a policy
with only `InvokeModel` fails at the first token with an error that looks nothing like a
permissions problem.

It also names two ARN shapes. A cross-region inference profile routes to a foundation
model in one of several regions, and the call is authorised against the profile and the
model it lands on. Granting only the profile denies at the routed region, which reads as
a model problem and is not one. Foundation-model ARNs carry no account id, so the region
wildcard covers every routed region in 239 characters.

**2. Enable the models** that are not already enabled. Bedrock console, us-east-1, Model
access: Anthropic Claude Sonnet 5 and Claude Haiku 4.5. Nova needs nothing - invoking
`amazon.nova-micro-v1:0`, which the pre-existing grant already allowed, returned a real
completion in 225 ms, so Nova model access is live in this account and the only thing
missing for Nova Lite was the ARN.

That test is also how the blocker was isolated. One model that worked and one that did
not, under the same credentials, separates an IAM problem from a model-enablement one.

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
