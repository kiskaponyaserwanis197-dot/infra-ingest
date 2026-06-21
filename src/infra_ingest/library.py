"""SQLite-backed research library index and retrieval helpers."""

import json
import re
import sqlite3
from pathlib import Path

import yaml

from .entities import extract_entities


DEFAULT_LIBRARY_DB = ".infra_ingest/library.sqlite"


def connect_library(db_path):
    """Open a library database and ensure schema exists."""
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn):
    """Create SQLite tables for notes and FTS search."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT,
            created TEXT,
            material_type TEXT,
            author TEXT,
            companies TEXT NOT NULL DEFAULT '[]',
            tickers TEXT NOT NULL DEFAULT '[]',
            industries TEXT NOT NULL DEFAULT '[]',
            metrics TEXT NOT NULL DEFAULT '[]',
            factors TEXT NOT NULL DEFAULT '[]',
            risk_events TEXT NOT NULL DEFAULT '[]',
            entities TEXT NOT NULL DEFAULT '[]',
            content TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path UNINDEXED,
            title,
            content,
            entities
        );

        CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_path TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            input_ref TEXT,
            event_date TEXT,
            tickers TEXT NOT NULL DEFAULT '[]',
            metrics TEXT NOT NULL DEFAULT '[]',
            factors TEXT NOT NULL DEFAULT '[]',
            backtest_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    add_missing_columns(
        conn,
        "notes",
        {
            "tickers": "TEXT NOT NULL DEFAULT '[]'",
            "metrics": "TEXT NOT NULL DEFAULT '[]'",
            "factors": "TEXT NOT NULL DEFAULT '[]'",
            "risk_events": "TEXT NOT NULL DEFAULT '[]'",
        },
    )
    conn.commit()


def add_missing_columns(conn, table, columns):
    """Add columns that may be missing from an existing SQLite database."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def index_note_file(db_path, note_path, glossary_terms=None):
    """Index a Markdown note into the research library."""
    note = parse_note_file(note_path, glossary_terms=glossary_terms)
    with connect_library(db_path) as conn:
        upsert_note(conn, note)
    return note


def index_note_dir(db_path, notes_dir, glossary_terms=None):
    """Index all Markdown notes under a directory."""
    indexed = []
    for note_path in sorted(Path(notes_dir).expanduser().rglob("*.md")):
        indexed.append(index_note_file(db_path, note_path, glossary_terms=glossary_terms))
    return indexed


def parse_note_file(note_path, glossary_terms=None):
    """Read Markdown content and normalized frontmatter metadata."""
    path = Path(note_path).expanduser().resolve()
    raw = path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(raw)
    title = metadata.get("title") or first_heading(body) or path.stem
    entities = metadata.get("entities") or extract_entities(raw, glossary_terms)
    companies = metadata.get("companies") or []
    tickers = metadata.get("tickers") or []
    industries = metadata.get("industries") or []
    metrics = metadata.get("metrics") or []
    factors = metadata.get("factors") or []
    risk_events = metadata.get("risk_events") or []
    return {
        "path": str(path),
        "title": title,
        "source": metadata.get("source"),
        "created": metadata.get("created"),
        "material_type": metadata.get("material_type"),
        "author": metadata.get("author"),
        "companies": _as_list(companies),
        "tickers": _as_list(tickers),
        "industries": _as_list(industries),
        "metrics": _as_list(metrics),
        "factors": _as_list(factors),
        "risk_events": _as_list(risk_events),
        "entities": _as_list(entities),
        "content": body.strip(),
    }


def split_frontmatter(markdown):
    """Split YAML frontmatter from a Markdown document."""
    if not markdown.startswith("---\n"):
        return {}, markdown
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, parts[2].lstrip()


def first_heading(markdown):
    """Return the first level-1 Markdown heading."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def upsert_note(conn, note):
    """Insert or replace a note and its FTS row."""
    payload = {
        **note,
        "companies": json.dumps(note["companies"], ensure_ascii=False),
        "tickers": json.dumps(note["tickers"], ensure_ascii=False),
        "industries": json.dumps(note["industries"], ensure_ascii=False),
        "metrics": json.dumps(note["metrics"], ensure_ascii=False),
        "factors": json.dumps(note["factors"], ensure_ascii=False),
        "risk_events": json.dumps(note["risk_events"], ensure_ascii=False),
        "entities": json.dumps(note["entities"], ensure_ascii=False),
    }
    conn.execute(
        """
        INSERT INTO notes (
            path, title, source, created, material_type, author,
            companies, tickers, industries, metrics, factors, risk_events,
            entities, content, updated_at
        )
        VALUES (
            :path, :title, :source, :created, :material_type, :author,
            :companies, :tickers, :industries, :metrics, :factors, :risk_events,
            :entities, :content, CURRENT_TIMESTAMP
        )
        ON CONFLICT(path) DO UPDATE SET
            title=excluded.title,
            source=excluded.source,
            created=excluded.created,
            material_type=excluded.material_type,
            author=excluded.author,
            companies=excluded.companies,
            tickers=excluded.tickers,
            industries=excluded.industries,
            metrics=excluded.metrics,
            factors=excluded.factors,
            risk_events=excluded.risk_events,
            entities=excluded.entities,
            content=excluded.content,
            updated_at=CURRENT_TIMESTAMP
        """,
        payload,
    )
    conn.execute("DELETE FROM notes_fts WHERE path = ?", (note["path"],))
    conn.execute(
        "INSERT INTO notes_fts(path, title, content, entities) VALUES (?, ?, ?, ?)",
        (
            note["path"],
            note["title"],
            note["content"],
            " ".join(
                note["entities"]
                + note["companies"]
                + note["tickers"]
                + note["industries"]
                + note["metrics"]
                + note["factors"]
                + note["risk_events"]
            ),
        ),
    )
    conn.commit()


def search_notes(
    db_path,
    query,
    *,
    source=None,
    company=None,
    ticker=None,
    industry=None,
    metric=None,
    factor=None,
    risk_event=None,
    date_from=None,
    date_to=None,
    limit=10,
):
    """Search notes with FTS and metadata filters."""
    with connect_library(db_path) as conn:
        sql = """
            SELECT n.*, bm25(notes_fts) AS score
            FROM notes_fts
            JOIN notes n ON n.path = notes_fts.path
            WHERE notes_fts MATCH ?
        """
        params = [fts_query(query)]
        sql, params = apply_filters(
            sql,
            params,
            source,
            company,
            ticker,
            industry,
            metric,
            factor,
            risk_event,
            date_from,
            date_to,
        )
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        return [row_to_result(row, query) for row in conn.execute(sql, params)]


def retrieve_context(db_path, question, **kwargs):
    """Retrieve compact source snippets for RAG."""
    results = search_notes(db_path, question, **kwargs)
    context = []
    for index, result in enumerate(results, start=1):
        context.append(
            {
                "ref": f"S{index}",
                "title": result["title"],
                "path": result["path"],
                "source": result["source"],
                "snippet": result["snippet"],
            }
        )
    return context


def apply_filters(sql, params, source, company, ticker, industry, metric, factor, risk_event, date_from, date_to):
    """Append optional metadata filters to a query."""
    if source:
        sql += " AND n.source LIKE ?"
        params.append(f"%{source}%")
    if company:
        sql += " AND n.companies LIKE ?"
        params.append(f"%{company}%")
    if ticker:
        sql += " AND n.tickers LIKE ?"
        params.append(f"%{ticker}%")
    if industry:
        sql += " AND n.industries LIKE ?"
        params.append(f"%{industry}%")
    if metric:
        sql += " AND n.metrics LIKE ?"
        params.append(f"%{metric}%")
    if factor:
        sql += " AND n.factors LIKE ?"
        params.append(f"%{factor}%")
    if risk_event:
        sql += " AND n.risk_events LIKE ?"
        params.append(f"%{risk_event}%")
    if date_from:
        sql += " AND n.created >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND n.created <= ?"
        params.append(date_to)
    return sql, params


def fts_query(query):
    """Build a conservative FTS query that works for English and Chinese text."""
    terms = re.findall(r"[\w\u4e00-\u9fff]+", query or "")
    return " OR ".join(terms) if terms else query


def row_to_result(row, query):
    """Convert a SQLite row into a search result."""
    content = row["content"]
    return {
        "path": row["path"],
        "title": row["title"],
        "source": row["source"],
        "created": row["created"],
        "material_type": row["material_type"],
        "companies": json.loads(row["companies"] or "[]"),
        "tickers": json.loads(row["tickers"] or "[]"),
        "industries": json.loads(row["industries"] or "[]"),
        "metrics": json.loads(row["metrics"] or "[]"),
        "factors": json.loads(row["factors"] or "[]"),
        "risk_events": json.loads(row["risk_events"] or "[]"),
        "entities": json.loads(row["entities"] or "[]"),
        "snippet": make_snippet(content, query),
        "score": row["score"],
    }


def make_snippet(content, query, size=180):
    """Return a compact snippet around the first query hit."""
    if not content:
        return ""
    lowered = content.lower()
    positions = [lowered.find(term.lower()) for term in re.findall(r"[\w\u4e00-\u9fff]+", query or "")]
    positions = [pos for pos in positions if pos >= 0]
    start = max(min(positions) - 40, 0) if positions else 0
    snippet = content[start : start + size].replace("\n", " ").strip()
    return snippet


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
