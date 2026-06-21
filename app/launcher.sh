#!/bin/bash

# Whisper转写 Launcher Script (with Boot Diagnostics & Architecture Resolution)
# Dynamically resolves python3 and checks for dependencies before launching
# Forces arm64 architecture on Apple Silicon Macs to avoid Rosetta/intel compatibility issues

# Force include Homebrew paths to ensure ffmpeg and yt-dlp are visible when launched from Finder
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

APP_DIR="$(dirname "$0")/.."
SCRIPT_PATH="$APP_DIR/Resources/whisper_gui.py"
APP_NAME="Whisper转写"
LOG_FILE="/tmp/whisper_boot.log"

echo "=== Whisper转写 启动日志 ===" > "$LOG_FILE"
echo "启动时间: $(date)" >> "$LOG_FILE"
echo "当前 PATH: $PATH" >> "$LOG_FILE"
echo "当前 USER: $USER" >> "$LOG_FILE"

# Detect if running on Apple Silicon
IS_ARM64=0
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
    IS_ARM64=1
    echo "系统架构: Apple Silicon (arm64)" >> "$LOG_FILE"
else
    echo "系统架构: Intel (x86_64)" >> "$LOG_FILE"
fi

# Show native macOS alert dialog on failure
show_alert() {
    local msg="$1"
    local title="$APP_NAME - 启动错误"
    osascript -e "display dialog \"$msg\" with title \"$title\" buttons {\"确定\"} default button \"确定\" with icon caution"
}

# Run python under native arm64 if on Apple Silicon
run_python() {
    if [ "$IS_ARM64" -eq 1 ]; then
        arch -arm64 "$RESOLVED_PYTHON" "$@"
    else
        "$RESOLVED_PYTHON" "$@"
    fi
}

# List of potential Python paths
PYTHON_CANDIDATES=(
    "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "/usr/bin/python3"
)

RESOLVED_PYTHON=""

# Try candidates
for candidate in "${PYTHON_CANDIDATES[@]}"; do
    echo "检测候选路径: $candidate" >> "$LOG_FILE"
    if [ -x "$candidate" ]; then
        RESOLVED_PYTHON="$candidate"
        echo "  ✓ 选中候选路径: $candidate" >> "$LOG_FILE"
        break
    fi
done

# Fallback to system path python3
if [ -z "$RESOLVED_PYTHON" ]; then
    echo "候选路径未命中，尝试从 PATH 查找 python3" >> "$LOG_FILE"
    if command -v python3 >/dev/null 2>&1; then
        RESOLVED_PYTHON=$(command -v python3)
        echo "  ✓ 从 PATH 选中: $RESOLVED_PYTHON" >> "$LOG_FILE"
    fi
fi

if [ -z "$RESOLVED_PYTHON" ]; then
    echo "❌ 失败: 未找到任何 Python 3 解释器" >> "$LOG_FILE"
    show_alert "未检测到 Python 3 环境。\n\n请在您的 Mac 上安装 Python 3 (建议版本 >= 3.10) 后再试。"
    exit 1
fi

echo "已选定 Python 路径: $RESOLVED_PYTHON" >> "$LOG_FILE"

# Check required libraries and capture error tracebacks
MISSING_LIBS=()

check_lib() {
    local lib="$1"
    local pip_name="$2"
    echo "检测依赖库: $lib" >> "$LOG_FILE"
    
    # Capture error output
    local err_output
    err_output=$(run_python -c "import $lib" 2>&1)
    local status=$?
    
    if [ $status -ne 0 ]; then
        echo "  ❌ 导入失败 ($lib):" >> "$LOG_FILE"
        echo "$err_output" >> "$LOG_FILE"
        MISSING_LIBS+=("$pip_name")
    else
        echo "  ✓ 导入成功 ($lib)" >> "$LOG_FILE"
    fi
}

check_lib "tkinter" "tkinter"
check_lib "faster_whisper" "faster-whisper"
check_lib "markitdown" "markitdown[pdf,docx,pptx,xlsx,xls]"
check_lib "requests" "requests"
check_lib "yaml" "PyYAML"

# Check if yt-dlp is available in common paths or PATH
YT_DLP_FOUND=0
YT_DLP_CANDIDATES=(
    "/opt/homebrew/bin/yt-dlp"
    "/usr/local/bin/yt-dlp"
)
for ytdl in "${YT_DLP_CANDIDATES[@]}"; do
    if [ -x "$ytdl" ]; then
        YT_DLP_FOUND=1
        break
    fi
done
if [ $YT_DLP_FOUND -eq 0 ] && command -v yt-dlp >/dev/null 2>&1; then
    YT_DLP_FOUND=1
fi

# Handle missing python libraries
if [ ${#MISSING_LIBS[@]} -ne 0 ]; then
    LIB_LIST=$(IFS=, ; echo "${MISSING_LIBS[*]}")
    INSTALL_CMD="$RESOLVED_PYTHON -m pip install ${LIB_LIST//,/ }"
    echo "❌ 启动失败: 缺少依赖库 [${LIB_LIST}]" >> "$LOG_FILE"
    show_alert "检测到缺少的 Python 依赖库: ${LIB_LIST}\n\n请打开终端并运行以下命令进行安装：\n\n${INSTALL_CMD}"
    exit 1
fi

# Check if ffmpeg is available. openai-whisper and yt-dlp both rely on it for
# common audio/video inputs, especially mp4/mov/webm files.
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "❌ 启动失败: 未找到 ffmpeg" >> "$LOG_FILE"
    show_alert "未找到音视频处理工具 ffmpeg。\n\n请确保已通过 Homebrew 安装 ffmpeg:\nbrew install ffmpeg"
    exit 1
fi

# Handle missing yt-dlp
if [ $YT_DLP_FOUND -eq 0 ]; then
    echo "❌ 启动失败: 未找到 yt-dlp" >> "$LOG_FILE"
    show_alert "未找到音频下载工具 yt-dlp。\n\n请确保已通过 Homebrew 安装 yt-dlp:\nbrew install yt-dlp"
    exit 1
fi

echo "🚀 所有依赖项检测通过，正在启动 whisper_gui.py..." >> "$LOG_FILE"

# Launch the Python GUI under correct architecture
if [ "$IS_ARM64" -eq 1 ]; then
    exec arch -arm64 "$RESOLVED_PYTHON" "$SCRIPT_PATH"
else
    exec "$RESOLVED_PYTHON" "$SCRIPT_PATH"
fi
