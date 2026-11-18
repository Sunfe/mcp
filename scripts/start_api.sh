#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# app.main reads APP_HOST and APP_PORT from the same .env as the MCP server.
exec .venv/bin/python -u -m app.main
