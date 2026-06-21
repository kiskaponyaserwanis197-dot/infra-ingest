"""Research run audit records stored alongside the local library."""

import json

from .library import connect_library


def record_research_run(
    db_path,
    *,
    note_path,
    manifest_path,
    input_ref,
    event_date=None,
    tickers=None,
    metrics=None,
    factors=None,
    backtest_result=None,
):
    """Persist a compact, queryable audit record for one research run."""
    with connect_library(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO research_runs (
                note_path, manifest_path, input_ref, event_date,
                tickers, metrics, factors, backtest_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                str(note_path),
                str(manifest_path),
                input_ref,
                event_date,
                json.dumps(tickers or [], ensure_ascii=False),
                json.dumps(metrics or [], ensure_ascii=False),
                json.dumps(factors or [], ensure_ascii=False),
                json.dumps(backtest_result or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_research_runs(db_path, limit=20):
    """Return recent research runs for inspection or tests."""
    with connect_library(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM research_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row_to_run(row) for row in rows]


def row_to_run(row):
    """Convert a SQLite row to a plain dictionary."""
    return {
        "id": row["id"],
        "note_path": row["note_path"],
        "manifest_path": row["manifest_path"],
        "input_ref": row["input_ref"],
        "event_date": row["event_date"],
        "tickers": json.loads(row["tickers"] or "[]"),
        "metrics": json.loads(row["metrics"] or "[]"),
        "factors": json.loads(row["factors"] or "[]"),
        "backtest": json.loads(row["backtest_json"] or "{}"),
        "created_at": row["created_at"],
    }

