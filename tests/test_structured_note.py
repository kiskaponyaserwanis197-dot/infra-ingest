from infra_ingest.structured_note import parse_note_json, render_structured_note_markdown


def test_parse_note_json_accepts_fenced_json_and_requires_evidence():
    note = parse_note_json(
        """
        ```json
        {
          "summary": "summary",
          "takeaways": [
            {
              "claim": "claim",
              "evidence": [{"source_ref": "[0.00s - 1.00s]", "snippet": "spoken text"}]
            }
          ],
          "concepts": [{"name": "IC", "explanation": "信息系数"}],
          "quiz": ["why?"],
          "atomic_notes": [{"title": "IC", "description": "记录指标定义"}],
          "financial_entities": {
            "companies": ["宁德时代"],
            "tickers": ["300750.SZ"],
            "industries": ["新能源"],
            "metrics": ["毛利率"],
            "factors": ["质量"],
            "risk_events": ["价格战风险"]
          },
          "material_fields": {"thesis": "盈利改善"},
          "investment_hypotheses": [{"hypothesis": "毛利率改善", "validation": "检验后续收益"}],
          "validation_questions": [{"question": "是否领先收益", "data_needed": "财务数据", "method": "事件研究"}],
          "backtest_ideas": [{"idea": "毛利率改善", "universe": "新能源", "signal": "毛利率同比改善", "horizon": "60日", "test": "分组回测"}]
        }
        ```
        """
    )

    markdown = render_structured_note_markdown(note)

    assert "来源：[0.00s - 1.00s]" in markdown
    assert "[[IC]]" in markdown
    assert note["financial_entities"]["tickers"] == ["300750.SZ"]
    assert "资料结构化字段" in markdown


def test_parse_note_json_rejects_missing_takeaways():
    try:
        parse_note_json('{"summary": "summary", "takeaways": []}')
    except ValueError as exc:
        assert "takeaways" in str(exc)
    else:
        raise AssertionError("expected validation error")
