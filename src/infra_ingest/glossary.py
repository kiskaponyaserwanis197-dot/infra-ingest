"""Domain glossary helpers for prompts and Whisper initial prompts."""

from pathlib import Path


DEFAULT_GLOSSARY_TERMS = [
    "Alpha",
    "Beta",
    "IC",
    "IR",
    "夏普比率",
    "最大回撤",
    "因子",
    "回测",
    "私募",
    "量化投资",
    "财报电话会",
    "专家访谈",
    "自由现金流",
    "毛利率",
    "净利率",
]


def load_glossary(path=None):
    """Load glossary terms from a newline-separated file, falling back to defaults."""
    terms = list(DEFAULT_GLOSSARY_TERMS)
    if path:
        glossary_path = Path(path).expanduser()
        if not glossary_path.exists():
            raise RuntimeError(f"专有名词词表不存在: {glossary_path}")
        loaded = [
            line.strip()
            for line in glossary_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        terms.extend(loaded)
    return dedupe_terms(terms)


def dedupe_terms(terms):
    """Return terms without duplicates while preserving order."""
    seen = set()
    result = []
    for term in terms:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result


def glossary_prompt_section(terms):
    """Render glossary terms for prompt injection."""
    if not terms:
        return "无"
    return "、".join(terms)


def merge_initial_prompt(initial_prompt, terms):
    """Combine user-provided Whisper prompt with glossary terms."""
    pieces = []
    if initial_prompt:
        pieces.append(initial_prompt.strip())
    if terms:
        pieces.append("，".join(terms))
    return "，".join(piece for piece in pieces if piece) or None
