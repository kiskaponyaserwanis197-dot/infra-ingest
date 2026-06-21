import json

from infra_ingest.backtest import run_event_study, write_backtest_result
from infra_ingest.quant_data import load_price_bars


def test_load_price_bars_parses_and_sorts_csv(tmp_path):
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "ticker,date,close,volume\n"
        "AAA,2026-01-02,110,2000\n"
        "AAA,2026-01-01,100,1000\n",
        encoding="utf-8",
    )

    bars = load_price_bars(csv_path)

    assert [bar["date"].isoformat() for bar in bars] == ["2026-01-01", "2026-01-02"]
    assert bars[0]["close"] == 100.0
    assert bars[0]["volume"] == 1000.0


def test_run_event_study_computes_forward_and_excess_returns(tmp_path):
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "ticker,date,close\n"
        "AAA,2026-01-01,100\n"
        "AAA,2026-01-02,110\n"
        "AAA,2026-01-03,121\n"
        "IDX,2026-01-01,100\n"
        "IDX,2026-01-02,105\n"
        "IDX,2026-01-03,110\n",
        encoding="utf-8",
    )

    result = run_event_study(
        csv_path,
        ["AAA"],
        event_date="2026-01-01",
        horizons=(1, 2),
        benchmark_ticker="IDX",
    )

    assert result["status"] == "ok"
    assert round(result["summary"]["1"]["average_return"], 6) == 0.1
    assert round(result["summary"]["1"]["average_excess_return"], 6) == 0.05
    assert round(result["observations"][1]["return"], 6) == 0.21


def test_run_event_study_skips_without_event_date(tmp_path):
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text("ticker,date,close\nAAA,2026-01-01,100\n", encoding="utf-8")

    result = run_event_study(csv_path, ["AAA"])

    assert result["status"] == "skipped"
    assert "--event-date" in result["reason"]


def test_write_backtest_result_creates_json_sidecar(tmp_path):
    note_path = tmp_path / "note.md"
    note_path.write_text("# Note", encoding="utf-8")
    result = {"status": "ok", "summary": {"1": {"average_return": 0.1}}}

    result_path = write_backtest_result(note_path, result)

    assert json.loads((tmp_path / "note.backtest.json").read_text(encoding="utf-8")) == result
    assert result_path == str(tmp_path / "note.backtest.json")
