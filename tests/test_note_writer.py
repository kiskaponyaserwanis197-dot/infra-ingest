from datetime import datetime

import yaml

from infra_ingest.note_writer import (
    build_note_metadata,
    generate_basic_note,
    parse_atomic_suggestions,
    render_frontmatter,
    resolve_target_dir,
    sanitize_title,
    unique_note_path,
    write_note,
)


def test_build_note_metadata_has_uniform_fields():
    metadata = build_note_metadata(
        title="Title",
        author="Author",
        source="source.txt",
        mode="basic",
        material_type="research_report",
        source_type="file",
        companies=["Company A"],
        industries=["AI"],
        entities=["Alpha"],
        now=datetime(2026, 6, 20, 1, 2, 3),
    )

    assert metadata["schema_version"]
    assert metadata["title"] == "Title"
    assert metadata["material_type"] == "research_report"
    assert metadata["companies"] == ["Company A"]
    assert metadata["tickers"] == []


def test_parse_atomic_suggestions_handles_backticked_wiki_links():
    output = "- `[[Alpha 因子]]`：记录因子定义\n- `[[IC]]`：记录预测能力"

    assert parse_atomic_suggestions(output) == "- [[Alpha 因子]]：记录因子定义\n- [[IC]]：记录预测能力"


def test_sanitize_title_removes_path_unsafe_characters():
    assert sanitize_title("A/B\\C:D#E") == "A-B-C-DE"


def test_sanitize_title_trims_and_defaults_empty_title():
    assert sanitize_title("  A/B  ") == "A-B"
    assert sanitize_title("   ") == "Untitled"


def test_generate_basic_note_uses_stable_timestamp():
    note = generate_basic_note(
        "Title",
        "Author",
        "source.txt",
        "body",
        now=datetime(2026, 6, 19, 8, 9, 10),
    )

    parsed = yaml.safe_load(note.split("---", 2)[1])
    assert parsed["created"] == "2026-06-19"
    assert "- **生成时间**: 2026-06-19 08:09:10" in note
    assert "body" in note
    assert "## 自动实体双链" in note


def test_frontmatter_is_yaml_safe():
    frontmatter = render_frontmatter(
        {
            "tags": ["source/ingested", "mode/basic"],
            "author": 'A: "quoted"',
            "source": "line 1\nline 2",
        }
    )

    assert frontmatter.startswith("---\n")
    assert "\n---" in frontmatter
    parsed = yaml.safe_load(frontmatter.split("---", 2)[1])
    assert parsed["author"] == 'A: "quoted"'
    assert parsed["source"] == "line 1\nline 2"


def test_resolve_target_dir_handles_absolute_and_relative(tmp_path):
    absolute = tmp_path / "out"

    assert resolve_target_dir(str(absolute), "/vault") == absolute
    assert resolve_target_dir("Clippings", "/vault").as_posix() == "/vault/Clippings"


def test_write_note_creates_markdown_file(tmp_path):
    path = write_note(tmp_path, "A/B", "content")

    assert path.endswith("A-B.md")
    assert (tmp_path / "A-B.md").read_text(encoding="utf-8") == "content"


def test_write_note_uses_unique_suffix_when_file_exists(tmp_path):
    first = write_note(tmp_path, "Same", "first")
    second = write_note(tmp_path, "Same", "second")

    assert first.endswith("Same.md")
    assert second != first
    assert second.endswith(".md")
    assert (tmp_path / "Same.md").read_text(encoding="utf-8") == "first"


def test_unique_note_path_adds_timestamp_suffix(tmp_path):
    (tmp_path / "Title.md").write_text("existing", encoding="utf-8")

    path = unique_note_path(tmp_path, "Title", now=datetime(2026, 6, 19, 1, 2, 3))

    assert path == tmp_path / "Title-20260619-010203.md"
