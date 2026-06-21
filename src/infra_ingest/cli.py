#!/usr/bin/env python3
"""CLI entry point for infra-ingest."""

import argparse
import json
import sys

from .glossary import load_glossary
from .library import DEFAULT_LIBRARY_DB, index_note_dir, search_notes
from .pipeline import run_pipeline
from .prompts import MATERIAL_TYPES
from .rag import answer_question
from .research_runs import list_research_runs

try:
    from rich.console import Console
except ImportError:
    class Console:
        def print(self, *args, **kwargs):
            print(*args, **kwargs)

        def log(self, *args, **kwargs):
            print("[log]", *args, **kwargs)


def build_parser():
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="infra-ingest: AI 自动化知识与研发协作管线")
    parser.add_argument("-i", "--input", help="输入的本地文件路径 (PDF/Office/HTML/文本/音视频等)")
    parser.add_argument("-o", "--output-dir", help="Obsidian 输出文件夹目录名 (默认写入 Clippings 目录)")
    parser.add_argument("--library-db", default=DEFAULT_LIBRARY_DB, help="研究库 SQLite 索引路径")
    parser.add_argument("--no-index", action="store_true", help="生成笔记后不自动写入研究库索引")
    parser.add_argument("--index-dir", help="索引某个目录下的 Markdown 笔记")
    parser.add_argument("--list-runs", action="store_true", help="列出最近的研究运行审计记录")
    parser.add_argument("--search", help="全文搜索研究库")
    parser.add_argument("--ask", help="基于研究库检索片段进行问答，需要配置 LLM")
    parser.add_argument("--limit", type=int, default=10, help="搜索或问答检索的最大结果数")
    parser.add_argument("--filter-source", help="按 source 元数据过滤")
    parser.add_argument("--filter-company", help="按 companies 元数据过滤")
    parser.add_argument("--filter-ticker", help="按 tickers 元数据过滤")
    parser.add_argument("--filter-industry", help="按 industries 元数据过滤")
    parser.add_argument("--filter-metric", help="按 metrics 元数据过滤")
    parser.add_argument("--filter-factor", help="按 factors 元数据过滤")
    parser.add_argument("--filter-risk-event", help="按 risk_events 元数据过滤")
    parser.add_argument("--filter-date-from", help="按 created 起始日期过滤，格式 YYYY-MM-DD")
    parser.add_argument("--filter-date-to", help="按 created 结束日期过滤，格式 YYYY-MM-DD")
    parser.add_argument("-m", "--model", default="base", help="Whisper 模型大小 (tiny/base/small/medium/large-v3, 默认 base)")
    parser.add_argument("-e", "--env", default=".env", help="自定义配置环境配置文件路径")
    parser.add_argument("--language", help="Whisper 识别语言代码，例如 zh/en/ja；不填则自动检测")
    parser.add_argument("--beam-size", type=int, default=None, help="Whisper beam size，越大越慢但通常更稳，建议 5-8")
    parser.add_argument("--initial-prompt", help="Whisper 领域提示词，用于补充专有名词、人名、公司名、术语")
    parser.add_argument("--glossary-file", help="专有名词词表文件，每行一个公司名、基金名或行业术语")
    parser.add_argument("--price-data-csv", help="本地行情数据 CSV，至少包含 ticker,date,close 列")
    parser.add_argument("--financial-data-csv", help="本地财务数据 CSV，至少包含 ticker,period 列")
    parser.add_argument("--event-date", help="文本观点/公告/电话会对应的事件日，格式 YYYY-MM-DD，用于前瞻收益事件研究")
    parser.add_argument("--benchmark-ticker", help="事件研究基准 ticker，用于计算超额收益")
    parser.add_argument(
        "--material-type",
        choices=sorted(MATERIAL_TYPES.keys()),
        default="auto",
        help="资料类型，用于选择 prompt: auto/research_report/earnings_call/announcement/expert_interview/podcast/meeting_minutes",
    )
    parser.add_argument("--device", default=None, help="Whisper 推理设备，默认读取 WHISPER_DEVICE 或 cpu")
    parser.add_argument("--compute-type", default=None, help="Whisper 计算精度，默认读取 WHISPER_COMPUTE_TYPE 或 int8")
    parser.add_argument("--no-vad", action="store_true", help="关闭 VAD 语音活动检测；默认开启以减少静音/噪音干扰")
    parser.add_argument("--no-llm", action="store_true", help="不调用 LLM，只把转写/提取内容保存为基础 Markdown")
    parser.add_argument("--cookies-browser", default="auto", help="URL 下载时的浏览器 Cookie 来源，例如 auto/chrome/edge/safari")
    parser.add_argument("--cookies-file", help="URL 下载时使用的 cookies.txt 文件路径")
    parser.add_argument("--title", help="自定义笔记标题 (默认使用文件名)")
    parser.add_argument("--author", default="Unknown", help="笔记作者/主讲人 (默认 Unknown)")
    parser.add_argument("--source", help="数据源链接或平台名 (默认使用文件名)")
    parser.add_argument("--company", action="append", default=[], help="为输出笔记写入公司 metadata，可重复传入")
    parser.add_argument("--industry", action="append", default=[], help="为输出笔记写入行业 metadata，可重复传入")
    parser.add_argument("--no-archive", action="store_true", help="不把处理后的输入文件复制到 raw archive")
    return parser


def main(argv=None):
    """Parse CLI args and run the ingest pipeline."""
    console = Console()
    args = build_parser().parse_args(argv)
    try:
        if args.index_dir:
            glossary_terms = load_glossary(args.glossary_file)
            indexed = index_note_dir(args.library_db, args.index_dir, glossary_terms=glossary_terms)
            console.print(f"[green]已索引 {len(indexed)} 篇 Markdown 笔记到: {args.library_db}[/green]")
            return 0

        if args.list_runs:
            runs = list_research_runs(args.library_db, limit=args.limit)
            for item in runs:
                console.print(
                    f"[cyan]{item['id']}. {item['created_at']}[/cyan] "
                    f"{', '.join(item['tickers']) or '无 ticker'} {item['note_path']}"
                )
                if item["backtest"]:
                    console.print(f"   回测: {json.dumps(item['backtest'].get('summary', {}), ensure_ascii=False)}")
            return 0

        filters = {
            "source": args.filter_source,
            "company": args.filter_company,
            "ticker": args.filter_ticker,
            "industry": args.filter_industry,
            "metric": args.filter_metric,
            "factor": args.filter_factor,
            "risk_event": args.filter_risk_event,
            "date_from": args.filter_date_from,
            "date_to": args.filter_date_to,
            "limit": args.limit,
        }
        if args.search:
            results = search_notes(args.library_db, args.search, **filters)
            for index, item in enumerate(results, start=1):
                console.print(f"[cyan]{index}. {item['title']}[/cyan] {item['created'] or ''} {item['path']}")
                console.print(f"   来源: {item['source'] or '未知'}")
                console.print(f"   片段: {item['snippet']}")
            return 0

        if args.ask:
            console.print(answer_question(args.library_db, args.ask, **filters))
            return 0

        if not args.input:
            raise RuntimeError("请提供 -i/--input，或使用 --index-dir、--search、--ask。")
        run_pipeline(args, console=console)
        return 0
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
