"""Audio and video transcription helpers for infra-ingest."""

from .transcript import format_segments_as_text

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    Progress = None
    SpinnerColumn = None
    TextColumn = None


def transcribe_audio(
    audio_path,
    model_size="base",
    language=None,
    beam_size=5,
    vad_filter=True,
    initial_prompt=None,
    device="cpu",
    compute_type="int8",
    console=None,
):
    """Transcribe an audio or video file with local faster-whisper."""
    if console:
        console.log(f"[yellow]正在初始化 Whisper 本地模型 ({model_size})...[/yellow]")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("未找到 faster-whisper 库，请使用 pip install -r requirements.txt 安装。") from exc

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        if console:
            console.log(f"[green]Whisper 模型 {model_size} 加载成功。开始转录音视频...[/green]")
            console.log(
                f"[dim]转写参数: device={device}, compute_type={compute_type}, "
                f"language={language or 'auto'}, beam_size={beam_size}, vad_filter={vad_filter}[/dim]"
            )

        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
        )
        if console:
            console.log(f"[green]转录音频语言检测为: {info.language} (概率: {info.language_probability:.2f})[/green]")

        segment_records = []
        if Progress is not None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task("语音识别中...", total=info.duration)
                for segment in segments:
                    segment_records.append(
                        {
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "text": segment.text.strip(),
                        }
                    )
                    progress.update(task, completed=segment.end)
        else:
            for segment in segments:
                segment_records.append(
                    {
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": segment.text.strip(),
                    }
                )

        return {
            "text": format_segments_as_text(segment_records),
            "segments": segment_records,
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration),
            "model": model_size,
        }
    except Exception as exc:
        raise RuntimeError(f"语音转录失败: {exc}") from exc
