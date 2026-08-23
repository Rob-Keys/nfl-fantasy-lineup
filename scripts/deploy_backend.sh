#!/usr/bin/env bash
set -euo pipefail

# Deploy the Lambda package and keep its timeout below the
# API Gateway HTTP API integration timeout.
AWS_REGION="${AWS_REGION:-us-east-1}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-fantasyLineupGenerator}"
LAMBDA_TIMEOUT_SECONDS="${LAMBDA_TIMEOUT_SECONDS:-29}"
LAMBDA_MEMORY_MB="${LAMBDA_MEMORY_MB:-512}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_dir="$(mktemp -d)"
package_file="${package_dir}/lambda.zip"
trap 'rm -rf "${package_dir}"' EXIT

cp -R "${repo_root}/fantasy_lineup" "${package_dir}/fantasy_lineup"
(cd "${repo_root}" && python3 -m pip install --quiet --target "${package_dir}" \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.14 \
  --only-binary=:all: -r requirements.txt)
(cd "${package_dir}" && zip -qr "${package_file}" . -x "$(basename "${package_file}")")

aws lambda update-function-configuration \
  --region "${AWS_REGION}" \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --runtime python3.14 \
  --handler fantasy_lineup.handler.lambda_handler \
  --timeout "${LAMBDA_TIMEOUT_SECONDS}" \
  --memory-size "${LAMBDA_MEMORY_MB}" \
  >/dev/null

aws lambda wait function-updated \
  --region "${AWS_REGION}" \
  --function-name "${LAMBDA_FUNCTION_NAME}"

aws lambda update-function-code \
  --region "${AWS_REGION}" \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --zip-file "fileb://${package_file}" \
  --publish \
  --query '{FunctionName:FunctionName,Version:Version,LastModified:LastModified}' \
  --output table
