from infra_ingest.library import index_note_file
from infra_ingest.rag import answer_question, validate_rag_answer


def test_answer_question_uses_retrieved_context(monkeypatch, tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\ntitle: Note\n---\n# Note\nAlpha 是一个信号。", encoding="utf-8")
    db = tmp_path / "library.sqlite"
    index_note_file(db, note)

    monkeypatch.setattr(
        "infra_ingest.rag.build_llm_config_from_env",
        lambda: {"api_key": "key", "base_url": "http://example.com/v1", "model": "fake"},
    )

    def fake_call(payload, system_prompt, config):
        assert "[S1]" in payload
        assert "Alpha 是一个信号" in payload
        return "Alpha 是一个信号。[S1]"

    monkeypatch.setattr("infra_ingest.rag.call_llm_api", fake_call)

    assert "Alpha" in answer_question(db, "Alpha 是什么")


def test_validate_rag_answer_warns_when_missing_citations():
    answer = validate_rag_answer("Alpha 是一个信号。", [{"ref": "S1"}])

    assert "没有标注任何检索来源" in answer


def test_validate_rag_answer_warns_on_invalid_citation():
    answer = validate_rag_answer("Alpha 是一个信号。[S2]", [{"ref": "S1"}])

    assert "不存在的来源编号" in answer
