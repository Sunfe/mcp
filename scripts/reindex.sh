#!/usr/bin/env bash
set -e
cd /home/liaozhic/data/mcp
source .venv/bin/activate
python -m app.ingest
