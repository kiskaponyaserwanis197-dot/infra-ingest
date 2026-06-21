"""Entity extraction and Obsidian link helpers."""

import re


def extract_entities(text, glossary_terms=None):
    """Extract glossary terms and existing wiki links from text."""
    entities = []
    for link in re.findall(r"\[\[([^\]]+)\]\]", text or ""):
        entities.append(link.strip())

    for term in glossary_terms or []:
        if term and term in text:
            entities.append(term)

    return dedupe_entities(entities)


def dedupe_entities(entities):
    """Deduplicate entity names while preserving order."""
    seen = set()
    result = []
    for entity in entities:
        normalized = entity.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def render_entity_links(entities):
    """Render entity names as Obsidian wiki links."""
    if not entities:
        return "- 暂无自动识别实体"
    return "\n".join(f"- [[{entity}]]" for entity in entities)
