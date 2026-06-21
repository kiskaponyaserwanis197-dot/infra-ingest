"""Markdown note rendering and writing helpers for infra-ingest."""

import re
from datetime import datetime
from pathlib import Path

import yaml

from .entities import render_entity_links


METADATA_SCHEMA_VERSION = "2026-06-20-v1"


def render_frontmatter(metadata):
    """Render safe YAML frontmatter for a Markdown note."""
    body = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{body}\n---"


def parse_atomic_suggestions(llm_output):
    """Extract Obsidian wiki links from an LLM response."""
    links = re.findall(r"-\s*`?(\[\[[^\]]+\]\])`?\s*[:：]\s*(.*)", llm_output)
    if not links:
        links = re.findall(r"(\[\[[^\]]+\]\])", llm_output)
        return "\n".join([f"- {link}：建议提取的原子概念" for link in links])

    return "\n".join([f"- {link}：{desc}" for link, desc in links])


def build_note_metadata(
    *,
    title,
    author,
    source,
    mode,
    material_type,
    source_type,
    companies=None,
    tickers=None,
    industries=None,
    metrics=None,
    factors=None,
    risk_events=None,
    entities=None,
    now=None,
):
    """Build unified note metadata for Markdown frontmatter and library filters."""
    current = now or datetime.now()
    return {
        "schema_version": METADATA_SCHEMA_VERSION,
        "title": title,
        "tags": ["source/ingested", f"mode/{mode}"],
        "created": current.strftime("%Y-%m-%d"),
        "author": author,
        "source": source,
        "source_type": source_type,
        "material_type": material_type,
        "companies": companies or [],
        "tickers": tickers or [],
        "industries": industries or [],
        "metrics": metrics or [],
        "factors": factors or [],
        "risk_events": risk_events or [],
        "entities": entities or [],
    }


def generate_source_note(title, author, source, llm_output, metadata=None, entities=None, now=None):
    """Render a structured Obsidian source note from LLM output."""
    concept_index = parse_atomic_suggestions(llm_output)
    metadata = metadata or build_note_metadata(
        title=title,
        author=author,
        source=source,
        mode="structured",
        material_type="auto",
        source_type="unknown",
        entities=entities or [],
        now=now,
    )
    if "status/unprocessed" not in metadata["tags"]:
        metadata["tags"].append("status/unprocessed")
    frontmatter = render_frontmatter(metadata)

    return f"""{frontmatter}
# 🎧 {title}

## 📌 核心概念索引

{concept_index if concept_index else "- 暂无建议的原子概念双链"}

## 🧭 自动实体双链

{render_entity_links(entities or metadata.get("entities", []))}

---

## 📝 AI 催化精要

{llm_output}
"""


def generate_basic_note(title, author, source, raw_text, mode_label="basic", metadata=None, entities=None, now=None):
    """Render a basic Markdown note when no LLM is configured."""
    current = now or datetime.now()
    metadata = metadata or build_note_metadata(
        title=title,
        author=author,
        source=source,
        mode=mode_label,
        material_type="auto",
        source_type="unknown",
        entities=entities or [],
        now=current,
    )
    frontmatter = render_frontmatter(metadata)

    return f"""{frontmatter}
# 🎧 {title}

## 基本信息

- **来源**: {source}
- **生成时间**: {current.strftime("%Y-%m-%d %H:%M:%S")}
- **处理模式**: 基础 Markdown，无 LLM 结构化

---

## 自动实体双链

{render_entity_links(entities or metadata.get("entities", []))}

---

## 转写 / 提取正文

{raw_text}
"""


def sanitize_title(title):
    """Sanitize a note title for filesystem and Obsidian compatibility."""
    safe_title = title.replace("/", "-").replace("\\", "-").replace(":", "-").replace("#", "")
    return safe_title.strip() or "Untitled"


def resolve_target_dir(output_dir, vault_path, default_folder="Clippings"):
    """Resolve a target folder from CLI/env settings."""
    target_folder_name = output_dir or default_folder
    target_folder = Path(target_folder_name).expanduser()
    if target_folder.is_absolute():
        return target_folder
    return Path(vault_path) / target_folder


def write_note(target_dir, title, content):
    """Write a Markdown note and return the output path."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file_path = unique_note_path(target_dir, title)
    target_file_path.write_text(content, encoding="utf-8")
    return str(target_file_path)


def unique_note_path(target_dir, title, now=None):
    """Return a non-overwriting note path, adding a unique suffix on collisions."""
    target_dir = Path(target_dir)
    safe_title = sanitize_title(title)
    candidate = target_dir / f"{safe_title}.md"
    if not candidate.exists():
        return candidate

    current = now or datetime.now()
    timestamp = current.strftime("%Y%m%d-%H%M%S")
    candidate = target_dir / f"{safe_title}-{timestamp}.md"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = target_dir / f"{safe_title}-{timestamp}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1
