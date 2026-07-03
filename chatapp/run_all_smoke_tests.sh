#!/usr/bin/env bash
set -euo pipefail

# One-click smoke tests for chatapp + ApiClient endpoints.
# Uses the active python environment (recommended: the same env you use to run ds_agent).

cd "$(dirname "$0")/.."

export CHATAPP_CONFIG_NAME="${CHATAPP_CONFIG_NAME:-multiturn_opchain_gpt5}"

python -m chatapp.smoke_test
