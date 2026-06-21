from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import json

from infra_ingest.pipeline import build_llm_output, run_pipeline, split_text


class DummyConsole:
    def __init__(self):
        self.messages = []

    def log(self, *args, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))


def make_args(input_path, output_dir, env_path):
    return SimpleNamespace(
        input=str(input_path),
        output_dir=str(output_dir),
        model="base",
        env=str(env_path),
        language=None,
        beam_size=None,
        initial_prompt=None,
        device=None,
        compute_type=None,
        no_vad=False,
        no_llm=True,
        cookies_browser="auto",
        cookies_file=None,
        glossary_file=None,
        price_data_csv=None,
        financial_data_csv=None,
        event_date=None,
        benchmark_ticker=None,
        material_type="auto",
        company=[],
        industry=[],
        no_index=True,
        library_db=str(output_dir / "library.sqlite"),
        title="Pipeline Smoke",
        author="Tester",
        source=None,
    )


def test_run_pipeline_writes_basic_note_for_plain_text(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    monkeypatch.delenv("TARGET_FOLDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    input_file = tmp_path / "input.txt"
    input_file.write_text("hello ingest", encoding="utf-8")
    output_dir = tmp_path / "out"
    args = make_args(input_file, output_dir, tmp_path / "missing.env")

    output_path = run_pipeline(args, console=DummyConsole(), script_dir=tmp_path)

    output = Path(output_path)
    assert output == output_dir / "Pipeline Smoke.md"
    content = output.read_text(encoding="utf-8")
    assert "mode/basic" in content
    assert "hello ingest" in content
    assert "量化投研增强" in content
    manifest = json.loads((output_dir / "Pipeline Smoke.manifest.json").read_text(encoding="utf-8"))
    assert manifest["input"]["ref"] == str(input_file)
    assert manifest["input"]["sha256"]
    assert manifest["models"]["whisper"] == "base"
    assert manifest["output"]["path"] == str(output)


def test_run_pipeline_writes_event_study_sidecar(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    monkeypatch.delenv("TARGET_FOLDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    input_file = tmp_path / "input.txt"
    input_file.write_text("宁德时代 300750.SZ 毛利率改善，质量因子可能有效。", encoding="utf-8")
    price_csv = tmp_path / "prices.csv"
    start = date(2026, 1, 1)
    rows = ["ticker,date,close"]
    for offset in range(61):
        day = start + timedelta(days=offset)
        rows.append(f"300750.SZ,{day.isoformat()},{100 + offset}")
        rows.append(f"000300.SH,{day.isoformat()},{100 + offset * 0.5}")
    price_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")

    output_dir = tmp_path / "out"
    args = make_args(input_file, output_dir, tmp_path / "missing.env")
    args.price_data_csv = str(price_csv)
    args.event_date = "2026-01-01"
    args.benchmark_ticker = "000300.SH"

    output_path = run_pipeline(args, console=DummyConsole(), script_dir=tmp_path)

    output = Path(output_path)
    content = output.read_text(encoding="utf-8")
    backtest = json.loads((output_dir / "Pipeline Smoke.backtest.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "Pipeline Smoke.manifest.json").read_text(encoding="utf-8"))

    assert "初步事件回测" in content
    assert backtest["status"] == "ok"
    assert backtest["benchmark_ticker"] == "000300.SH"
    assert manifest["quant"]["event_study_status"] == "ok"
    assert manifest["quant"]["datasets"]["prices"]["sha256"]
    assert manifest["quant"]["datasets"]["prices"]["row_count"] == 122
    assert manifest["output"]["backtest_path"].endswith(".backtest.json")


def test_split_text_keeps_all_content_with_overlap():
    chunks = split_text("abcdefghij", chunk_size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]


def test_build_llm_output_chunks_long_text(monkeypatch):
    calls = []

    def fake_call(text_content, system_prompt, config):
        calls.append((text_content, system_prompt))
        if len(calls) < 3:
            return f"summary-{len(calls)}"
        return """
        {
          "summary": "final summary",
          "takeaways": [
            {
              "claim": "claim with evidence",
              "evidence": [{"source_ref": "分块 1", "snippet": "abc"}]
            }
          ],
          "concepts": [{"name": "Alpha", "explanation": "factor"}],
          "quiz": ["question?"],
          "atomic_notes": [{"title": "Alpha", "description": "factor note"}]
        }
        """

    monkeypatch.setenv("LLM_CHUNK_CHAR_LIMIT", "5")
    monkeypatch.setenv("LLM_CHUNK_OVERLAP", "0")
    monkeypatch.setattr("infra_ingest.pipeline.call_llm_api", fake_call)

    output = build_llm_output("abcdefghij", {"model": "fake"}, DummyConsole())

    assert output["summary"] == "final summary"
    assert len(calls) == 3
    assert "分块 1/2" in calls[0][0]
    assert "分块 2/2" in calls[1][0]
    assert "分块摘要" in calls[2][0]


def test_build_llm_output_parses_json_schema(monkeypatch):
    def fake_call(text_content, system_prompt, config):
        assert "合法 JSON 对象" in system_prompt
        assert "专家访谈" in system_prompt
        return """
        ```json
        {
          "summary": "one sentence",
          "takeaways": [
            {
              "claim": "重要结论",
              "evidence": [{"source_ref": "[1.00s - 2.00s]", "snippet": "原文片段"}]
            }
          ],
          "concepts": [],
          "quiz": [],
          "atomic_notes": []
        }
        ```
        """

    monkeypatch.setattr("infra_ingest.pipeline.call_llm_api", fake_call)

    output = build_llm_output("raw", {"model": "fake"}, DummyConsole(), "expert_interview", ["Alpha"])

    assert output["takeaways"][0]["evidence"][0]["source_ref"] == "[1.00s - 2.00s]"
