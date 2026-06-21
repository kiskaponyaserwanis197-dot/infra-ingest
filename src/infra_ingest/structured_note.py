"""Structured LLM note parsing, validation, and Markdown rendering."""

import json
import re


NOTE_SCHEMA_VERSION = "2026-06-20-v2"


NOTE_JSON_SCHEMA = {
    "type": "object",
    "required": ["summary", "takeaways", "concepts", "quiz", "atomic_notes"],
    "properties": {
        "summary": {"type": "string"},
        "takeaways": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim", "evidence"],
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["source_ref", "snippet"],
                            "properties": {
                                "source_ref": {"type": "string"},
                                "snippet": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "explanation"],
                "properties": {
                    "name": {"type": "string"},
                    "explanation": {"type": "string"},
                    "evidence": {"type": "array"},
                },
            },
        },
        "quiz": {"type": "array", "items": {"type": "string"}},
        "atomic_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "description"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "financial_entities": {
            "type": "object",
            "properties": {
                "companies": {"type": "array", "items": {"type": "string"}},
                "tickers": {"type": "array", "items": {"type": "string"}},
                "industries": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "factors": {"type": "array", "items": {"type": "string"}},
                "risk_events": {"type": "array", "items": {"type": "string"}},
            },
        },
        "material_fields": {
            "type": "object",
            "description": "Material-specific fields for research reports, announcements, earnings calls, interviews, podcasts, or meeting minutes.",
        },
        "investment_hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "string"},
                    "validation": {"type": "string"},
                    "evidence": {"type": "array"},
                },
            },
        },
        "validation_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "data_needed": {"type": "string"},
                    "method": {"type": "string"},
                },
            },
        },
        "backtest_ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idea": {"type": "string"},
                    "universe": {"type": "string"},
                    "signal": {"type": "string"},
                    "horizon": {"type": "string"},
                    "test": {"type": "string"},
                },
            },
        },
    },
}


def parse_note_json(llm_output):
    """Parse an LLM JSON object, accepting fenced JSON as a fallback."""
    text = llm_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM output did not contain a JSON object")
        data = json.loads(match.group(0))

    return normalize_note_json(data)


def normalize_note_json(data):
    """Validate and normalize the structured note shape used by the renderer."""
    if not isinstance(data, dict):
        raise ValueError("structured note must be a JSON object")

    normalized = {
        "summary": _string(data.get("summary")),
        "takeaways": [],
        "concepts": [],
        "quiz": [],
        "atomic_notes": [],
        "financial_entities": normalize_financial_entities(data.get("financial_entities")),
        "material_fields": data.get("material_fields") if isinstance(data.get("material_fields"), dict) else {},
        "investment_hypotheses": [],
        "validation_questions": [],
        "backtest_ideas": [],
    }
    if not normalized["summary"]:
        raise ValueError("structured note missing required field: summary")

    for item in _list(data.get("takeaways")):
        claim = _string(item.get("claim") if isinstance(item, dict) else item)
        if not claim:
            continue
        evidence = []
        if isinstance(item, dict):
            for source in _list(item.get("evidence")):
                if isinstance(source, dict):
                    source_ref = _string(source.get("source_ref"))
                    snippet = _string(source.get("snippet"))
                else:
                    source_ref = ""
                    snippet = _string(source)
                if source_ref or snippet:
                    evidence.append({"source_ref": source_ref or "未标注", "snippet": snippet})
        normalized["takeaways"].append({"claim": claim, "evidence": evidence})

    for item in _list(data.get("concepts")):
        if not isinstance(item, dict):
            continue
        name = _string(item.get("name"))
        explanation = _string(item.get("explanation"))
        if name and explanation:
            normalized["concepts"].append(
                {
                    "name": name,
                    "explanation": explanation,
                    "evidence": _list(item.get("evidence")),
                }
            )

    normalized["quiz"] = [_string(item) for item in _list(data.get("quiz")) if _string(item)]
    for item in _list(data.get("atomic_notes")):
        if isinstance(item, dict):
            title = _string(item.get("title"))
            description = _string(item.get("description"))
        else:
            title = _string(item)
            description = ""
        if title:
            normalized["atomic_notes"].append({"title": title, "description": description})

    normalized["investment_hypotheses"] = [
        item for item in _list(data.get("investment_hypotheses")) if isinstance(item, dict)
    ]
    normalized["validation_questions"] = [
        item for item in _list(data.get("validation_questions")) if isinstance(item, dict)
    ]
    normalized["backtest_ideas"] = [
        item for item in _list(data.get("backtest_ideas")) if isinstance(item, dict)
    ]

    if not normalized["takeaways"]:
        raise ValueError("structured note missing required field: takeaways")
    return normalized


def normalize_financial_entities(value):
    """Normalize optional finance entity fields."""
    if not isinstance(value, dict):
        value = {}
    return {
        "companies": [_string(item) for item in _list(value.get("companies")) if _string(item)],
        "tickers": [_string(item) for item in _list(value.get("tickers")) if _string(item)],
        "industries": [_string(item) for item in _list(value.get("industries")) if _string(item)],
        "metrics": [_string(item) for item in _list(value.get("metrics")) if _string(item)],
        "factors": [_string(item) for item in _list(value.get("factors")) if _string(item)],
        "risk_events": [_string(item) for item in _list(value.get("risk_events")) if _string(item)],
    }


def render_structured_note_markdown(note):
    """Render a normalized structured note as Markdown."""
    lines = [
        "### 1. 核心硬核结论",
        "",
        note["summary"],
        "",
    ]

    for index, item in enumerate(note["takeaways"], start=1):
        lines.append(f"{index}. {item['claim']}")
        for evidence in item.get("evidence", []):
            ref = evidence.get("source_ref") or "未标注"
            snippet = evidence.get("snippet") or ""
            lines.append(f"   - 来源：{ref}；片段：{snippet}")
    lines.extend(["", "### 2. 底层概念解构", ""])

    for item in note["concepts"]:
        lines.append(f"- **{item['name']}**：{item['explanation']}")

    lines.extend(["", "### 3. 主动召回测试", ""])
    for index, question in enumerate(note["quiz"], start=1):
        lines.append(f"{index}. {question}")

    lines.extend(["", "### 4. 原子笔记建议", ""])
    for item in note["atomic_notes"]:
        title = item["title"].strip("[]")
        lines.append(f"- [[{title}]]：{item.get('description', '')}")

    fields = note.get("material_fields") or {}
    if fields:
        lines.extend(["", "### 5. 资料结构化字段", ""])
        for key, value in fields.items():
            if value:
                lines.append(f"- **{key}**：{_format_value(value)}")

    return "\n".join(lines).strip()


def _format_value(value):
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if isinstance(value, dict):
        return "；".join(f"{key}: {val}" for key, val in value.items())
    return str(value)


def _list(value):
    return value if isinstance(value, list) else []


def _string(value):
    return str(value).strip() if value is not None else ""
