from infra_ingest.entities import extract_entities, render_entity_links


def test_extract_entities_uses_wiki_links_and_glossary():
    entities = extract_entities("讨论 [[宁德时代]] 和 Alpha 因子", ["Alpha", "Beta"])

    assert entities == ["宁德时代", "Alpha"]


def test_render_entity_links_outputs_obsidian_links():
    assert render_entity_links(["宁德时代"]) == "- [[宁德时代]]"
