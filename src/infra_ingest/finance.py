"""Finance-specific entity extraction and quant research templates."""

import csv
import re
from pathlib import Path


INDUSTRY_TERMS = [
    "新能源",
    "半导体",
    "医药",
    "消费",
    "白酒",
    "银行",
    "证券",
    "保险",
    "地产",
    "军工",
    "汽车",
    "互联网",
    "人工智能",
    "云计算",
    "光伏",
    "储能",
]

METRIC_TERMS = [
    "营收",
    "收入",
    "净利润",
    "扣非净利润",
    "毛利率",
    "净利率",
    "ROE",
    "ROA",
    "EPS",
    "PE",
    "PB",
    "PS",
    "自由现金流",
    "经营现金流",
    "资本开支",
    "库存周转",
    "应收账款",
    "订单",
]

FACTOR_TERMS = [
    "Alpha",
    "Beta",
    "动量",
    "反转",
    "价值",
    "成长",
    "质量",
    "盈利",
    "低波",
    "小市值",
    "拥挤度",
    "换手率",
    "IC",
    "IR",
    "因子暴露",
]

RISK_TERMS = [
    "风险",
    "下滑",
    "不及预期",
    "监管",
    "诉讼",
    "减值",
    "违约",
    "价格战",
    "汇率",
    "原材料",
    "产能过剩",
    "地缘政治",
]

COMPANY_STOP_TERMS = set(INDUSTRY_TERMS + METRIC_TERMS + FACTOR_TERMS + [
    "量化投资",
    "私募",
    "因子",
    "回测",
    "最大回撤",
    "夏普比率",
])


def extract_financial_entities(text, glossary_terms=None):
    """Extract finance-oriented entities from unstructured text."""
    text = text or ""
    companies = []
    for term in glossary_terms or []:
        if term and term in text and is_company_candidate(term):
            companies.append(term)
    companies.extend(re.findall(r"([\u4e00-\u9fa5A-Za-z0-9]{2,24}(?:股份|集团|公司|银行|证券|保险))", text))
    companies.extend(
        re.findall(
            r"([\u4e00-\u9fa5]{2,12})\s+(?=(?:[036]\d{5}\.(?:SH|SZ)|\d{4}\.HK|[A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b)",
            text,
        )
    )

    tickers = re.findall(
        r"\b(?:[A-Z]{1,5}(?:\.[A-Z]{1,3})?|[036]\d{5}\.(?:SH|SZ)|\d{4}\.HK)\b",
        text,
    )
    industries = [term for term in INDUSTRY_TERMS if term in text]
    metrics = [term for term in METRIC_TERMS if term in text]
    factors = [term for term in FACTOR_TERMS if term in text]
    risk_events = extract_risk_events(text)
    return {
        "companies": dedupe(companies),
        "tickers": dedupe(tickers),
        "industries": dedupe(industries),
        "metrics": dedupe(metrics),
        "factors": dedupe(factors),
        "risk_events": risk_events,
    }


def merge_financial_entities(*items):
    """Merge multiple finance entity dictionaries."""
    merged = {
        "companies": [],
        "tickers": [],
        "industries": [],
        "metrics": [],
        "factors": [],
        "risk_events": [],
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in merged:
            merged[key].extend(item.get(key) or [])
    return {key: dedupe(values) for key, values in merged.items()}


def extract_risk_events(text):
    """Return short text snippets containing risk terms."""
    snippets = []
    for sentence in re.split(r"[。！？\n]", text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        if any(term in sentence for term in RISK_TERMS):
            snippets.append(sentence[:160])
    return dedupe(snippets)


def is_company_candidate(term):
    """Return True when a glossary term looks like a company rather than a metric."""
    term = str(term).strip()
    if not term or term in COMPANY_STOP_TERMS:
        return False
    if re.fullmatch(r"[A-Z]{1,5}", term):
        return False
    if any(suffix in term for suffix in ["公司", "集团", "股份", "银行", "证券", "保险"]):
        return True
    return len(term) >= 4 and bool(re.search(r"[\u4e00-\u9fa5]", term))


def load_market_data_summary(price_csv=None, financial_csv=None):
    """Load lightweight local CSV data summaries for validation prompts."""
    return {
        "prices": summarize_csv(price_csv, ["ticker", "date", "close"]) if price_csv else None,
        "financials": summarize_csv(financial_csv, ["ticker", "period"]) if financial_csv else None,
    }


def summarize_csv(path, key_columns):
    """Summarize a CSV file without loading it into a heavy dataframe dependency."""
    csv_path = Path(path).expanduser()
    if not csv_path.exists():
        raise RuntimeError(f"数据文件不存在: {csv_path}")

    row_count = 0
    columns = []
    tickers = set()
    min_date = None
    max_date = None
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        missing = [column for column in key_columns if column not in columns]
        if missing:
            raise RuntimeError(f"数据文件缺少列 {missing}: {csv_path}")
        for row in reader:
            row_count += 1
            if row.get("ticker"):
                tickers.add(row["ticker"])
            date_value = row.get("date") or row.get("period")
            if date_value:
                min_date = date_value if min_date is None or date_value < min_date else min_date
                max_date = date_value if max_date is None or date_value > max_date else max_date

    return {
        "path": str(csv_path),
        "columns": columns,
        "row_count": row_count,
        "tickers": sorted(tickers),
        "min_date": min_date,
        "max_date": max_date,
    }


def build_investment_hypotheses(note=None, finance_entities=None):
    """Create investment hypotheses from structured takeaways and extracted entities."""
    note = note or {}
    finance_entities = finance_entities or {}
    hypotheses = []
    for item in note.get("investment_hypotheses", []):
        if isinstance(item, dict):
            hypotheses.append(item)
    for takeaway in note.get("takeaways", [])[:3]:
        claim = takeaway.get("claim") if isinstance(takeaway, dict) else str(takeaway)
        if claim:
            hypotheses.append(
                {
                    "hypothesis": claim,
                    "validation": "用价格、财务指标或行业数据验证该观点是否可重复观察。",
                }
            )
    if not hypotheses and finance_entities.get("metrics"):
        metric = finance_entities["metrics"][0]
        hypotheses.append(
            {
                "hypothesis": f"{metric} 的边际变化可能解释后续收益或估值变化。",
                "validation": f"检验 {metric} 环比/同比改善后 1-3 个月的超额收益。",
            }
        )
    return hypotheses


def build_validation_questions(finance_entities, data_summary=None):
    """Generate data-verifiable research questions from extracted finance entities."""
    data_summary = data_summary or {}
    questions = []
    tickers = finance_entities.get("tickers") or finance_entities.get("companies") or ["目标公司"]
    metrics = finance_entities.get("metrics") or ["核心财务指标"]
    factors = finance_entities.get("factors") or []

    for target in tickers[:3]:
        for metric in metrics[:2]:
            questions.append(
                {
                    "question": f"{target} 的 {metric} 改善是否领先未来收益或估值修复？",
                    "data_needed": "价格序列、财务报表指标、行业对比样本",
                    "method": "构造事件窗口或分组回测，对比改善组与未改善组的后续收益。",
                }
            )

    for factor in factors[:2]:
        questions.append(
            {
                "question": f"{factor} 在相关行业或股票池中是否仍有稳定 IC？",
                "data_needed": "因子暴露、未来收益、行业和市值中性化变量",
                "method": "计算 Rank IC、分层收益和换手率，观察不同市场阶段的稳定性。",
            }
        )

    if data_summary.get("prices"):
        questions.append(
            {
                "question": "资料观点是否能在已接入行情数据覆盖区间内复现？",
                "data_needed": data_summary["prices"]["path"],
                "method": "使用本地行情 CSV 生成信号并进行样本内/样本外对比。",
            }
        )
    return questions


def build_backtest_ideas(finance_entities, material_type="auto"):
    """Build text-to-backtest idea templates."""
    metrics = finance_entities.get("metrics") or ["营收", "毛利率"]
    factors = finance_entities.get("factors") or ["质量"]
    industries = finance_entities.get("industries") or ["全市场"]
    ideas = []
    ideas.append(
        {
            "idea": f"{metrics[0]} 边际改善事件驱动",
            "universe": industries[0],
            "signal": f"{metrics[0]} 同比或环比改善，且公告/电话会文本情绪不恶化",
            "horizon": "20/60/120 个交易日",
            "test": "按改善幅度分组，计算超额收益、最大回撤、胜率和换手率。",
        }
    )
    ideas.append(
        {
            "idea": f"{factors[0]} 因子文本确认",
            "universe": industries[0],
            "signal": f"传统 {factors[0]} 因子高分，同时资料中出现正向经营验证线索",
            "horizon": "月度调仓",
            "test": "比较纯量化因子与文本确认后的组合收益、IC 和回撤。",
        }
    )
    if material_type == "earnings_call":
        ideas.append(
            {
                "idea": "财报电话会指引修正策略",
                "universe": industries[0],
                "signal": "管理层上调需求、利润率或资本开支指引，且分析师问答风险较少",
                "horizon": "财报后 1-3 个月",
                "test": "以电话会日期为事件日，回测指引改善样本的事件后超额收益。",
            }
        )
    return ideas


def render_quant_research_section(
    finance_entities,
    note=None,
    data_summary=None,
    material_sections=None,
    material_type="auto",
    backtest_result=None,
):
    """Render finance entities, hypotheses, validation questions, and backtest ideas."""
    note = note or {}
    hypotheses = build_investment_hypotheses(note, finance_entities)
    questions = note.get("validation_questions") or build_validation_questions(finance_entities, data_summary)
    ideas = note.get("backtest_ideas") or build_backtest_ideas(finance_entities, material_type)
    fields = note.get("material_fields") or {}
    fields = {**(material_sections or {}), **fields}

    lines = ["### 6. 量化投研增强", "", "#### 金融实体", ""]
    for key, label in [
        ("companies", "公司"),
        ("tickers", "Ticker"),
        ("industries", "行业"),
        ("metrics", "指标"),
        ("factors", "因子"),
        ("risk_events", "风险事件"),
    ]:
        values = finance_entities.get(key) or []
        lines.append(f"- **{label}**：{', '.join(values) if values else '未识别'}")

    if fields:
        lines.extend(["", "#### 结构化资料字段", ""])
        for key, value in fields.items():
            if not value:
                continue
            lines.append(f"- **{key}**：{format_value(value)}")

    lines.extend(["", "#### 投资假设", ""])
    for item in hypotheses:
        lines.append(f"- {item.get('hypothesis', '')}")
        if item.get("validation"):
            lines.append(f"  - 验证：{item['validation']}")

    lines.extend(["", "#### 待验证问题", ""])
    for item in questions:
        lines.append(f"- {item.get('question', '')}")
        lines.append(f"  - 数据：{item.get('data_needed', '待补充')}")
        lines.append(f"  - 方法：{item.get('method', '待设计')}")

    lines.extend(["", "#### 回测想法模板", ""])
    for item in ideas:
        lines.append(f"- **{item.get('idea', '')}**")
        lines.append(f"  - 股票池：{item.get('universe', '待定义')}")
        lines.append(f"  - 信号：{item.get('signal', '待定义')}")
        lines.append(f"  - 周期：{item.get('horizon', '待定义')}")
        lines.append(f"  - 检验：{item.get('test', '待定义')}")

    if backtest_result:
        lines.extend(["", "#### 初步事件回测", ""])
        lines.extend(render_backtest_result(backtest_result))

    return "\n".join(lines).strip()


def render_backtest_result(result):
    """Render a compact event-study result for Markdown notes."""
    if result.get("status") != "ok":
        return [f"- 状态：跳过", f"- 原因：{result.get('reason', '未说明')}"]

    lines = [
        f"- 事件日：{result.get('event_date')}",
        f"- 样本：{', '.join(result.get('tickers') or [])}",
    ]
    if result.get("benchmark_ticker"):
        lines.append(f"- 基准：{result['benchmark_ticker']}")
    if result.get("warnings"):
        lines.append(f"- 警告：{'；'.join(result['warnings'])}")
    lines.append("- 汇总：")
    for horizon, stats in (result.get("summary") or {}).items():
        summary = (
            f"{horizon} 个交易日，样本 {stats.get('sample_size', 0)}，"
            f"平均收益 {format_pct(stats.get('average_return'))}，"
            f"胜率 {format_pct(stats.get('hit_rate'))}"
        )
        if stats.get("average_excess_return") is not None:
            summary += f"，平均超额 {format_pct(stats.get('average_excess_return'))}"
        lines.append(f"  - {summary}")
    return lines


def format_pct(value):
    """Format a decimal return as percentage text."""
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def format_value(value):
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if isinstance(value, dict):
        return "；".join(f"{key}: {val}" for key, val in value.items())
    return str(value)


def dedupe(values):
    seen = set()
    result = []
    for value in values:
        normalized = str(value).strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
