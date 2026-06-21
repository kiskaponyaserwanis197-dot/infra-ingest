from infra_ingest.glossary import load_glossary, merge_initial_prompt


def test_load_glossary_merges_defaults_and_file_terms(tmp_path):
    glossary = tmp_path / "glossary.txt"
    glossary.write_text("# comment\n宁德时代\nAlpha\n", encoding="utf-8")

    terms = load_glossary(glossary)

    assert "宁德时代" in terms
    assert terms.count("Alpha") == 1


def test_merge_initial_prompt_keeps_user_prompt_first():
    prompt = merge_initial_prompt("用户词", ["Alpha", "Beta"])

    assert prompt.startswith("用户词")
    assert "Alpha" in prompt
