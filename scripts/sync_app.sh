#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${1:-/Applications/Whisper转写.app}"
CONTENTS_DIR="$APP_DIR/Contents"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
MACOS_DIR="$CONTENTS_DIR/MacOS"
BACKEND_DIR="$RESOURCES_DIR/infra-ingest"
BACKUP_DIR="/tmp/whisper_app_sync_backup/$(date +%Y%m%d_%H%M%S)"

if [[ ! -d "$CONTENTS_DIR" ]]; then
  echo "App bundle not found: $APP_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -R "$RESOURCES_DIR" "$BACKUP_DIR/Resources"
cp -R "$MACOS_DIR" "$BACKUP_DIR/MacOS"

mkdir -p "$BACKEND_DIR" "$MACOS_DIR"

rm -f \
  "$BACKEND_DIR/config.py" \
  "$BACKEND_DIR/document_parser.py" \
  "$BACKEND_DIR/infra_ingest.py" \
  "$BACKEND_DIR/converters.py" \
  "$BACKEND_DIR/sources.py" \
  "$BACKEND_DIR/llm_client.py" \
  "$BACKEND_DIR/manifest.py" \
  "$BACKEND_DIR/note_writer.py" \
  "$BACKEND_DIR/pipeline.py" \
  "$BACKEND_DIR/prompts.py" \
  "$BACKEND_DIR/transcriber.py"

cp "$ROOT_DIR/main.py" "$BACKEND_DIR/"
cp "$ROOT_DIR/pyproject.toml" "$BACKEND_DIR/"
rm -rf "$BACKEND_DIR/src"
cp -R "$ROOT_DIR/src" "$BACKEND_DIR/src"
cp "$ROOT_DIR/requirements.txt" "$BACKEND_DIR/"
cp "$ROOT_DIR/requirements-app.txt" "$BACKEND_DIR/"
cp "$ROOT_DIR/.env.example" "$BACKEND_DIR/"
rm -rf "$BACKEND_DIR/examples"
cp -R "$ROOT_DIR/examples" "$BACKEND_DIR/examples"

cp "$ROOT_DIR/app/whisper_gui.py" "$RESOURCES_DIR/whisper_gui.py"
cp "$ROOT_DIR/app/launcher.sh" "$MACOS_DIR/Whisper转写"
chmod +x "$MACOS_DIR/Whisper转写"

rm -rf "$RESOURCES_DIR/__pycache__" "$BACKEND_DIR/__pycache__" "$BACKEND_DIR/src/infra_ingest/__pycache__"

echo "Synced project to: $APP_DIR"
echo "Backup saved to: $BACKUP_DIR"
