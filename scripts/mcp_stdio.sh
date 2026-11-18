#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# stdout is reserved for MCP JSON-RPC. Send diagnostics to stderr.
if [[ ! -x .venv/bin/python ]]; then
  echo "Project Python not found: create .venv and install requirements.txt first." >&2
  exit 1
fi
export PYTHONIOENCODING=utf-8
exec .venv/bin/python -u -m app.mcp_server
