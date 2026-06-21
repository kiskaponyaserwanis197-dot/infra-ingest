"""Lightweight knowledge graph export for ingested notes."""

import json
from pathlib import Path

from .library import parse_note_file


def graph_path_for_library(db_path):
    """Return the graph export path next to the library database."""
    return str(Path(db_path).expanduser().parent / "graph.json")


def update_graph_from_note(db_path, note_path, glossary_terms=None):
    """Add or update one note in the local graph export."""
    graph_path = Path(graph_path_for_library(db_path))
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph = load_graph(graph_path)
    note = parse_note_file(note_path, glossary_terms=glossary_terms)
    remove_note_edges(graph, note["path"])
    add_note_graph(graph, note)
    write_graph(graph_path, graph)
    return str(graph_path)


def load_graph(path):
    """Load a graph JSON file or return an empty graph."""
    if not Path(path).exists():
        return {"nodes": [], "edges": []}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_graph(path, graph):
    """Write a deterministic graph JSON file."""
    graph["nodes"] = sorted(unique_items(graph["nodes"], "id"), key=lambda item: item["id"])
    graph["edges"] = sorted(unique_items(graph["edges"], "id"), key=lambda item: item["id"])
    Path(path).write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_note_graph(graph, note):
    """Add note, entity, and finance relationships to the graph."""
    note_id = f"note:{note['path']}"
    graph["nodes"].append({"id": note_id, "type": "note", "label": note["title"], "path": note["path"]})
    relation_fields = [
        ("companies", "company", "mentions_company"),
        ("tickers", "ticker", "mentions_ticker"),
        ("industries", "industry", "mentions_industry"),
        ("metrics", "metric", "mentions_metric"),
        ("factors", "factor", "mentions_factor"),
        ("entities", "entity", "mentions_entity"),
    ]
    for field, node_type, relation in relation_fields:
        for value in note.get(field, []):
            node_id = f"{node_type}:{value}"
            graph["nodes"].append({"id": node_id, "type": node_type, "label": value})
            edge_id = f"{note_id}->{relation}->{node_id}"
            graph["edges"].append({"id": edge_id, "source": note_id, "target": node_id, "type": relation})


def remove_note_edges(graph, note_path):
    """Remove an existing note node and outgoing edges before re-adding it."""
    note_id = f"note:{note_path}"
    graph["nodes"] = [node for node in graph.get("nodes", []) if node.get("id") != note_id]
    graph["edges"] = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("source") != note_id and not str(edge.get("id", "")).startswith(f"{note_id}->")
    ]


def unique_items(items, key):
    """Deduplicate a list of dictionaries by a key."""
    seen = set()
    result = []
    for item in items:
        value = item.get(key)
        if value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result
