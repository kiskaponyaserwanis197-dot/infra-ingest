"""Prompt templates used by infra-ingest."""

import json

from .glossary import glossary_prompt_section
from .structured_note import NOTE_JSON_SCHEMA, NOTE_SCHEMA_VERSION


PROMPT_VERSION = "2026-06-20-v3"

MATERIAL_TYPES = {
    "auto": "自动识别资料类型",
    "research_report": "研报",
    "earnings_call": "财报电话会",
    "announcement": "公告",
    "expert_interview": "专家访谈",
    "podcast": "播客",
    "meeting_minutes": "会议纪要",
}

MATERIAL_GUIDANCE = {
    "auto": "先判断资料类型，再按最贴近的类型提炼；不要编造资料中没有的上下文。",
    "research_report": "重点提取投资结论、关键假设、估值或指标口径、风险因素、可复核的数据出处。material_fields 应包含 thesis、assumptions、valuation_metrics、risks。",
    "earnings_call": "区分管理层陈述和问答；重点提取业绩驱动、指引、资本开支、利润率、风险和时间点。",
    "announcement": "重点提取公告事项、涉及主体、金额或比例、发生日期、影响路径、约束条件和风险。",
    "expert_interview": "区分专家观点、事实依据和推测；重点保留行业机制、供需变化、验证线索和不确定性。",
    "podcast": "保留时间戳线索；重点提取观点推进、案例、反例、可复述的概念和主持/嘉宾的明确判断。",
    "meeting_minutes": "重点提取决策、待办、负责人、截止时间、争议点和后续跟进；避免把讨论过程误写成已决定事项。material_fields 应包含 decisions、action_items、owners、deadlines。",
}


def build_system_prompt(material_type="auto", glossary_terms=None):
    """Build the final structured-note prompt for a material type."""
    material_type = material_type if material_type in MATERIAL_TYPES else "auto"
    glossary = glossary_prompt_section(glossary_terms or [])
    guidance = MATERIAL_GUIDANCE[material_type]
    schema = json.dumps(NOTE_JSON_SCHEMA, ensure_ascii=False, indent=2)
    return f"""
你是严谨的投研资料整理助手。请只基于用户提供的原文输出，不要补充外部事实。

资料类型：{MATERIAL_TYPES[material_type]}
类型处理要求：{guidance}
专有名词词表：{glossary}

输出必须是一个合法 JSON 对象，不要输出 Markdown，不要包裹 ```json 代码块。
JSON 必须符合 schema 版本 {NOTE_SCHEMA_VERSION} 的字段语义：
{schema}

硬性要求：
1. takeaways 中每条 claim 都必须至少附带一个 evidence。
2. evidence.source_ref 优先使用时间戳，例如 [12.30s - 18.20s]；没有时间戳时使用页码、小标题、段落位置或“原文片段”。
3. evidence.snippet 必须是原文中的短片段或紧贴原文的摘录，不要写泛泛解释。
4. concepts 只提取原文中出现或能被原文明确定义的概念。
5. quiz 只输出问题，不输出答案。
6. atomic_notes.title 不要带 [[ ]]，渲染层会自动加双链。
7. financial_entities 尽量抽取公司、ticker、行业、指标、因子、风险事件；没有就返回空数组。
8. investment_hypotheses 必须是可被数据验证的假设，不要写无法观测的主观判断。
9. validation_questions 需要写明 data_needed 和 method。
10. backtest_ideas 需要写明 universe、signal、horizon、test。
""".strip()

CHUNK_SUMMARY_PROMPT = """
请作为投研资料整理助手，先不要写最终 Obsidian 笔记。
你正在处理一份长资料的其中一个分块。请只基于当前分块输出：

### 分块核心信息
- 本分块最重要的事实、观点、数据或论证。

### 关键概念与实体
- 公司、行业、指标、人物、术语、风险点。

### 可追溯线索
- 保留原文中的页码、时间戳、小标题或其他定位线索；没有则写“无明确线索”。

要求：不要编造当前分块没有的信息；不要输出最终原子笔记建议。
""".strip()


def build_chunk_summary_prompt(material_type="auto", glossary_terms=None):
    """Build a chunk prompt with material-specific context."""
    material_type = material_type if material_type in MATERIAL_TYPES else "auto"
    glossary = glossary_prompt_section(glossary_terms or [])
    return f"""
{CHUNK_SUMMARY_PROMPT}

资料类型：{MATERIAL_TYPES[material_type]}
类型处理要求：{MATERIAL_GUIDANCE[material_type]}
专有名词词表：{glossary}
""".strip()
