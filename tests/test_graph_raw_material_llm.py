import requests

from infra_ingest.graph import load_graph, update_graph_from_note
from infra_ingest.llm_client import call_llm_api
from infra_ingest.material_parser import parse_material_sections
from infra_ingest.raw_archive import archive_source


def test_archive_source_copies_to_raw_folder(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")
    db = tmp_path / "state" / "library.sqlite"

    archived = archive_source(source, "abcdef1234567890", db)

    assert archived.endswith("input.txt")
    assert (tmp_path / "state" / "raw").is_dir()
    assert "content" in open(archived, encoding="utf-8").read()


def test_update_graph_from_note_adds_finance_nodes(tmp_path):
    note = tmp_path / "note.md"
    note.write_text(
        """---
title: Note
companies: [宁德时代]
tickers: [300750.SZ]
industries: [新能源]
metrics: [毛利率]
factors: [质量]
entities: [宁德时代, 毛利率]
---
# Note
body
""",
        encoding="utf-8",
    )
    db = tmp_path / "state" / "library.sqlite"

    graph_path = update_graph_from_note(db, note)
    graph = load_graph(graph_path)
    node_ids = {node["id"] for node in graph["nodes"]}

    assert "company:宁德时代" in node_ids
    assert "ticker:300750.SZ" in node_ids
    assert any(edge["type"] == "mentions_metric" for edge in graph["edges"])


def test_parse_material_sections_extracts_research_report_sections():
    sections = parse_material_sections(
        "核心观点：毛利率改善。风险提示：价格战可能加剧。",
        "research_report",
    )

    assert "core_thesis" in sections
    assert "risks" in sections


def test_call_llm_api_uses_fallback_after_primary_failure(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, ok):
            self.ok = ok
            self.text = "error"

        def raise_for_status(self):
            if not self.ok:
                raise requests.HTTPError("boom", response=self)

        def json(self):
            return {"choices": [{"message": {"content": "fallback-ok"}}]}

    def fake_post(url, **kwargs):
        calls.append(url)
        return FakeResponse(ok=len(calls) == 2)

    monkeypatch.setattr("infra_ingest.llm_client.requests.post", fake_post)

    output = call_llm_api(
        "text",
        "system",
        {
            "api_key": "primary",
            "base_url": "https://primary.example/v1",
            "model": "primary-model",
            "timeout": 1,
            "temperature": 0.1,
            "fallback": {
                "api_key": "fallback",
                "base_url": "https://fallback.example/v1",
                "model": "fallback-model",
                "timeout": 1,
                "temperature": 0.1,
            },
        },
    )

    assert output == "fallback-ok"
    assert calls == [
        "https://primary.example/v1/chat/completions",
        "https://fallback.example/v1/chat/completions",
    ]
