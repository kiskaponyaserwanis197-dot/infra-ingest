from infra_ingest.research_runs import list_research_runs, record_research_run


def test_record_research_run_persists_quant_audit_payload(tmp_path):
    db = tmp_path / "library.sqlite"

    run_id = record_research_run(
        db,
        note_path="/tmp/note.md",
        manifest_path="/tmp/note.manifest.json",
        input_ref="report.pdf",
        event_date="2026-01-01",
        tickers=["AAA"],
        metrics=["毛利率"],
        factors=["质量"],
        backtest_result={"status": "ok"},
    )
    runs = list_research_runs(db)

    assert run_id == 1
    assert runs[0]["tickers"] == ["AAA"]
    assert runs[0]["metrics"] == ["毛利率"]
    assert runs[0]["backtest"]["status"] == "ok"

