"""URL source helpers for infra-ingest."""

import re
import shutil
import subprocess
import html
import os
import time
from pathlib import Path
from urllib.parse import urlparse
import requests


def is_url(value):
    """Return True when the input looks like an HTTP(S) URL."""
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _find_yt_dlp():
    path = shutil.which("yt-dlp")
    if path:
        return path
    for candidate in ["/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp"]:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("未找到 yt-dlp。请先运行: brew install yt-dlp")


def _cookie_args_for_url(url, cookies_browser="auto", cookies_file=None):
    if cookies_file:
        return ["--cookies", str(Path(cookies_file).expanduser())]

    if "bilibili" not in url.lower() and "b23.tv" not in url.lower():
        return []

    if cookies_browser and cookies_browser.lower() not in {"auto", "自动", "自动 (auto)"}:
        return ["--cookies-from-browser", cookies_browser.lower()]

    local_cookie_file = Path.home() / "Downloads" / "cookies.txt"
    if local_cookie_file.exists():
        return ["--cookies", str(local_cookie_file)]

    return []


def _request_with_retries(method, url, *, retries=3, timeout=30, stream=False, headers=None):
    """Run an HTTP request with small retry handling and clearer errors."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                stream=stream,
            )
            if 400 <= response.status_code < 500:
                raise RuntimeError(f"HTTP {response.status_code} 客户端错误: {url}")
            if response.status_code >= 500:
                raise requests.HTTPError(f"HTTP {response.status_code} 服务端错误", response=response)
            response.raise_for_status()
            return response
        except RuntimeError:
            raise
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(0.5 * attempt)
        except requests.RequestException as exc:
            raise RuntimeError(f"网络请求失败: {url}. 错误: {exc}") from exc

    raise RuntimeError(f"网络请求重试 {retries} 次后仍失败: {url}. 最后错误: {last_error}")


def download_audio_from_url(
    url,
    workdir,
    cookies_browser="auto",
    cookies_file=None,
    logger=None,
    timeout=None,
):
    """Download a URL as a local mp3 using yt-dlp."""
    yt_dlp = _find_yt_dlp()
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    timeout = timeout or int(os.getenv("YT_DLP_TIMEOUT", "900"))

    lower_url = url.lower()
    referer_args = []
    ua_args = []
    if "bilibili" in lower_url or "b23.tv" in lower_url:
        referer_args = ["--referer", "https://www.bilibili.com/"]
        ua_args = [
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        ]

    cmd = [
        yt_dlp,
        *_cookie_args_for_url(url, cookies_browser, cookies_file),
        *referer_args,
        *ua_args,
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "-o",
        "audio.%(ext)s",
        "--no-playlist",
        url,
    ]

    if logger:
        logger(f"正在通过 yt-dlp 提取音频: {url}")

    try:
        process = subprocess.run(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"yt-dlp 下载超时 ({timeout}s): {url}") from exc

    if process.returncode != 0:
        if "xiaoyuzhoufm.com" in url.lower():
            if logger:
                logger("yt-dlp 未直接解析小宇宙，尝试从页面提取音频地址")
            return _download_xiaoyuzhou_audio(url, workdir)
        tail = "\n".join(process.stdout.splitlines()[-20:])
        raise RuntimeError(f"yt-dlp 下载失败:\n{tail}")

    downloaded = sorted(workdir.glob("audio.*"))
    if not downloaded:
        raise RuntimeError("yt-dlp 执行成功但未找到输出音频文件")
    return downloaded[0]


def _download_xiaoyuzhou_audio(url, workdir):
    """Best-effort fallback for Xiaoyuzhou episode pages."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.xiaoyuzhoufm.com/",
    }
    response = _request_with_retries(
        "GET",
        url,
        headers=headers,
        timeout=30,
        retries=3,
    )
    page = html.unescape(response.text).replace("\\u002F", "/")
    candidates = re.findall(r"https?://[^\"'<> ]+\.(?:mp3|m4a|aac)(?:\?[^\"'<> ]*)?", page)
    if not candidates:
        raise RuntimeError("未能从小宇宙页面中提取到 mp3/m4a 音频地址")

    audio_url = candidates[0]
    audio_response = _request_with_retries(
        "GET",
        audio_url,
        stream=True,
        timeout=60,
        retries=3,
        headers=headers,
    )
    suffix = ".m4a" if ".m4a" in audio_url.lower() else ".mp3"
    audio_path = Path(workdir) / f"audio{suffix}"
    with open(audio_path, "wb") as f:
        for chunk in audio_response.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    return audio_path


def title_from_url(url):
    """Create a readable fallback title from a URL."""
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5_-]+", "-", parsed.path.strip("/"))
    return f"{host}-{slug}".strip("-") or host
