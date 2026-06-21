import json

from infra_ingest.transcript import format_segments_as_text, write_segments


def test_format_segments_as_text_preserves_timestamps():
    text = format_segments_as_text(
        [{"start": 1.0, "end": 2.5, "text": "hello"}]
    )

    assert text == "[1.00s - 2.50s] hello"


def test_write_segments_writes_sidecar_json(tmp_path):
    output = tmp_path / "note.md"
    output.write_text("note", encoding="utf-8")

    path = write_segments(
        output,
        {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}]},
    )

    data = json.loads((tmp_path / "note.segments.json").read_text(encoding="utf-8"))
    assert path.endswith("note.segments.json")
    assert data["segments"][0]["text"] == "hello"
