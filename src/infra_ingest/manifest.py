"""Processing manifest helpers for infra-ingest."""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

from .prompts import PROMPT_VERSION


def sha256_file(path, chunk_size=1024 * 1024):
    """Return a sha256 hash for a local file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    input_ref,
    input_path,
    input_is_url,
    file_hash,
    raw_archive_path,
    output_path,
    segments_path,
    graph_path,
    backtest_path=None,
    backtest_result=None,
    data_summary=None,
    llm_config,
    args,
    started_at,
    completed_at=None,
):
    """Build a JSON-serializable manifest for an ingest run."""
    completed = completed_at or datetime.now()
    return {
        "input": {
            "ref": input_ref,
            "type": "url" if input_is_url else "file",
            "processed_path": str(input_path),
            "raw_archive_path": str(raw_archive_path) if raw_archive_path else None,
            "sha256": file_hash,
        },
        "processing": {
            "run_id": uuid.uuid4().hex,
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": round((completed - started_at).total_seconds(), 3),
        },
        "models": {
            "llm": llm_config.get("model") if llm_config else None,
            "whisper": args.model,
        },
        "prompt": {
            "version": PROMPT_VERSION,
            "material_type": getattr(args, "material_type", "auto"),
        },
        "output": {
            "path": str(output_path),
            "segments_path": str(segments_path) if segments_path else None,
            "graph_path": str(graph_path) if graph_path else None,
            "backtest_path": str(backtest_path) if backtest_path else None,
        },
        "quant": {
            "price_data_csv": getattr(args, "price_data_csv", None),
            "financial_data_csv": getattr(args, "financial_data_csv", None),
            "event_date": getattr(args, "event_date", None),
            "benchmark_ticker": getattr(args, "benchmark_ticker", None),
            "event_study_status": backtest_result.get("status") if backtest_result else None,
            "datasets": build_dataset_snapshots(data_summary),
        },
    }


def write_manifest(output_path, manifest):
    """Write a manifest JSON file next to the generated Markdown note."""
    manifest_path = Path(output_path).with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(manifest_path)


def build_dataset_snapshots(data_summary):
    """Attach file hashes to compact dataset summaries for reproducibility."""
    snapshots = {}
    for name, summary in (data_summary or {}).items():
        if not summary:
            snapshots[name] = None
            continue
        payload = dict(summary)
        path = payload.get("path")
        payload["sha256"] = sha256_file(path) if path and Path(path).exists() else None
        snapshots[name] = payload
    return snapshots
