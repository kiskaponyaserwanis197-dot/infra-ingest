"""Transcript segment data structures."""

import json
from pathlib import Path


def format_segments_as_text(segments):
    """Render transcript segments as timestamped plain text."""
    return "\n".join(
        f"[{segment['start']:.2f}s - {segment['end']:.2f}s] {segment['text']}"
        for segment in segments
    )


def write_segments(output_path, transcription):
    """Write transcript segment metadata next to a generated note."""
    if not transcription:
        return None

    segment_path = Path(output_path).with_suffix(".segments.json")
    segment_path.write_text(
        json.dumps(transcription, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(segment_path)
