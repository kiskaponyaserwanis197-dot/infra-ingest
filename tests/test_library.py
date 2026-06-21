from infra_ingest.library import index_note_file, search_notes


def test_library_indexes_and_filters_markdown_notes(tmp_path):
    note = tmp_path / "note.md"
    note.write_text(
        """---
schema_version: 2026-06-20-v1
title: AI 研报
created: '2026-06-20'
source: report.pdf
material_type: research_report
author: Analyst
companies:
- 宁德时代
tickers:
- 300750.SZ
industries:
- 新能源
metrics:
- 毛利率
factors:
- 质量
risk_events:
- 价格战风险
entities:
- 毛利率
---
# AI 研报

宁德时代 毛利率 出现改善。
""",
        encoding="utf-8",
    )
    db = tmp_path / "library.sqlite"

    indexed = index_note_file(db, note)
    results = search_notes(
        db,
        "毛利率",
        company="宁德时代",
        ticker="300750.SZ",
        industry="新能源",
        metric="毛利率",
        factor="质量",
        risk_event="价格战",
    )

    assert indexed["title"] == "AI 研报"
    assert len(results) == 1
    assert results[0]["source"] == "report.pdf"
    assert results[0]["tickers"] == ["300750.SZ"]


def test_library_search_returns_empty_when_filter_misses(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\ntitle: Note\ncompanies: [A]\n---\n# Note\nAlpha content", encoding="utf-8")
    db = tmp_path / "library.sqlite"

    index_note_file(db, note)

    assert search_notes(db, "Alpha", company="B") == []
