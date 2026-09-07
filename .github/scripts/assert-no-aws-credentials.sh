#!/usr/bin/env bash
# The demo and the test suite must run with no cloud credentials at all.
#
# Checking AWS_ACCESS_KEY_ID alone is not enough: botocore will also pick up a session
# token, a shared credentials file, a container or IMDS endpoint, or a web-identity
# token. Any of those present means the "no credentials required" claim is untested.
set -euo pipefail

VARS=(
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN
  AWS_SECURITY_TOKEN
  AWS_PROFILE
  AWS_DEFAULT_PROFILE
  AWS_ROLE_ARN
  AWS_WEB_IDENTITY_TOKEN_FILE
  AWS_SHARED_CREDENTIALS_FILE
  AWS_CONFIG_FILE
  AWS_CONTAINER_CREDENTIALS_FULL_URI
  AWS_CONTAINER_CREDENTIALS_RELATIVE_URI
)

found=()
for name in "${VARS[@]}"; do
  if [ -n "${!name-}" ]; then
    found+=("$name")
  fi
done

if [ -d "${HOME}/.aws" ]; then
  found+=("~/.aws directory")
fi

if [ ${#found[@]} -gt 0 ]; then
  echo "::error::AWS credential sources are visible to this job: ${found[*]}"
  echo "The demo must run without them, so this check fails rather than passing silently."
  exit 1
fi

echo "no AWS credential source present, as required"
