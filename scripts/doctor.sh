#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

echo "infra-ingest doctor"
echo "项目目录: $ROOT_DIR"
echo "Python: $($PYTHON_BIN -c 'import sys; print(sys.executable)')"
echo "Python 版本: $($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "✓ $name: $(command -v "$name")"
  else
    echo "✗ 缺少 $name"
    return 1
  fi
}

check_py() {
  local module="$1"
  local package="$2"
  if "$PYTHON_BIN" -c "import $module" >/dev/null 2>&1; then
    echo "✓ Python 模块: $module"
  else
    echo "✗ 缺少 Python 模块: $module，安装建议: $PYTHON_BIN -m pip install $package"
    return 1
  fi
}

status=0
check_py rich rich || status=1
check_py requests requests || status=1
check_py yaml PyYAML || status=1
check_py markitdown "markitdown[pdf,docx,pptx,xlsx,xls]" || status=1
check_py faster_whisper faster-whisper || status=1
check_cmd ffmpeg || status=1
check_cmd yt-dlp || status=1

if [[ -f "$ROOT_DIR/main.py" && -d "$ROOT_DIR/src/infra_ingest" ]]; then
  echo "✓ 后端入口正常"
else
  echo "✗ 后端入口缺失"
  status=1
fi

if [[ $status -eq 0 ]]; then
  echo "检查通过。可以运行: ./run gui"
else
  echo "检查未完全通过。可先运行: ./run install，并确认 brew install ffmpeg yt-dlp"
fi
exit "$status"

