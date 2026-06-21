"""Lightweight section parsing for investment research materials."""

import re


SECTION_KEYWORDS = {
    "research_report": {
        "investment_rating": ["投资评级", "评级"],
        "core_thesis": ["核心观点", "投资要点", "投资逻辑", "核心结论"],
        "earnings_forecast": ["盈利预测", "业绩预测"],
        "valuation": ["估值", "目标价"],
        "risks": ["风险提示", "风险因素"],
    },
    "earnings_call": {
        "management_remarks": ["管理层", "经营回顾", "业绩回顾"],
        "guidance": ["指引", "展望", "全年目标"],
        "qa": ["问答", "Q&A", "分析师问答"],
        "margins_capex_cashflow": ["毛利率", "资本开支", "现金流"],
        "risks": ["风险", "挑战"],
    },
    "announcement": {
        "event": ["公告事项", "事项", "交易", "收购", "合同", "中标"],
        "parties": ["涉及主体", "交易对方", "公司"],
        "amount_or_ratio": ["金额", "比例", "占比"],
        "date": ["日期", "时间"],
        "impact": ["影响", "有利于", "预计"],
        "risks": ["风险", "不确定性"],
    },
}


def parse_material_sections(text, material_type="auto"):
    """Extract coarse material-specific sections with keyword matching."""
    material_type = material_type if material_type in SECTION_KEYWORDS else "research_report"
    sentences = split_sentences(text)
    sections = {key: [] for key in SECTION_KEYWORDS[material_type]}
    for sentence in sentences:
        for section, keywords in SECTION_KEYWORDS[material_type].items():
            if any(keyword in sentence for keyword in keywords):
                sections[section].append(sentence)
    return {key: values[:5] for key, values in sections.items() if values}


def split_sentences(text):
    """Split Chinese/English text into compact sentence-like chunks."""
    chunks = re.split(r"(?<=[。！？!?])\s+|[\n\r]+", text or "")
    return [chunk.strip()[:220] for chunk in chunks if chunk.strip()]
