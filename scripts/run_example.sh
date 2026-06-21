#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 main.py \
  -i examples/input.txt \
  -o "$ROOT_DIR/outputs" \
  --title "infra-ingest example" \
  --no-llm
