from infra_ingest.finance import (
    build_backtest_ideas,
    build_validation_questions,
    extract_financial_entities,
    load_market_data_summary,
    render_quant_research_section,
)


def test_extract_financial_entities_finds_quant_terms():
    text = "宁德时代 300750.SZ 属于新能源行业，毛利率改善但存在价格战风险，质量因子可能有效。"

    entities = extract_financial_entities(text, ["宁德时代"])

    assert entities["companies"] == ["宁德时代"]
    assert entities["tickers"] == ["300750.SZ"]
    assert "新能源" in entities["industries"]
    assert "毛利率" in entities["metrics"]
    assert "质量" in entities["factors"]
    assert entities["risk_events"]


def test_extract_financial_entities_does_not_treat_metric_glossary_as_company():
    text = "宁德时代 毛利率 改善，质量因子可能有效。"

    entities = extract_financial_entities(text, ["宁德时代", "毛利率", "因子"])

    assert entities["companies"] == ["宁德时代"]
    assert "毛利率" in entities["metrics"]


def test_load_market_data_summary_reads_local_csv(tmp_path):
    price_csv = tmp_path / "prices.csv"
    price_csv.write_text("ticker,date,close\n300750.SZ,2026-01-01,100\n", encoding="utf-8")
    financial_csv = tmp_path / "financials.csv"
    financial_csv.write_text("ticker,period,revenue\n300750.SZ,2025Q4,10\n", encoding="utf-8")

    summary = load_market_data_summary(price_csv, financial_csv)

    assert summary["prices"]["row_count"] == 1
    assert summary["financials"]["tickers"] == ["300750.SZ"]


def test_quant_templates_generate_validation_and_backtest_ideas():
    entities = {
        "companies": ["宁德时代"],
        "tickers": ["300750.SZ"],
        "industries": ["新能源"],
        "metrics": ["毛利率"],
        "factors": ["质量"],
        "risk_events": [],
    }

    questions = build_validation_questions(entities)
    ideas = build_backtest_ideas(entities, "earnings_call")
    section = render_quant_research_section(entities, material_type="earnings_call")

    assert "毛利率" in questions[0]["question"]
    assert any("电话会" in idea["idea"] for idea in ideas)
    assert "回测想法模板" in section
