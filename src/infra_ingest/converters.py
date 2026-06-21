"""Local file-to-Markdown adapters for infra-ingest."""

from pathlib import Path


AUDIO_VIDEO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".mov",
    ".flac",
    ".ogg",
    ".aac",
    ".mkv",
    ".webm",
}

PLAIN_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}

MARKITDOWN_PREFERRED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".epub",
    ".ipynb",
    ".zip",
    ".msg",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
}


def read_plain_text(path):
    """Read a UTF-8 text or Markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def convert_local_file_to_markdown(path):
    """
    Convert a local document into Markdown using Microsoft MarkItDown.

    MarkItDown can also handle URLs, but infra-ingest intentionally calls the
    narrower local-file API to keep this project local-first.
    """
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError(
            "未安装 MarkItDown。请先运行: pip install -r requirements.txt"
        ) from exc

    converter = MarkItDown(enable_plugins=False)
    result = converter.convert_local(Path(path))
    markdown = getattr(result, "markdown", str(result))
    if not markdown or not markdown.strip():
        raise RuntimeError("MarkItDown 未提取到可用 Markdown 内容")
    return markdown


def should_try_markitdown(path):
    """Return True when the file is a non-media document worth routing through MarkItDown."""
    return Path(path).suffix.lower() not in AUDIO_VIDEO_EXTENSIONS
