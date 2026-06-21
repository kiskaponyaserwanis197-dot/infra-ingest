"""Small, dependency-light market data helpers for quant research workflows."""

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


REQUIRED_PRICE_COLUMNS = ["ticker", "date", "close"]


def load_price_bars(path):
    """Load daily price bars from a CSV file.

    The CSV must contain ticker,date,close. Optional numeric columns such as
    open/high/low/volume are preserved when present.
    """
    csv_path = Path(path).expanduser()
    if not csv_path.exists():
        raise RuntimeError(f"行情数据文件不存在: {csv_path}")

    bars = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        missing = [column for column in REQUIRED_PRICE_COLUMNS if column not in columns]
        if missing:
            raise RuntimeError(f"行情数据缺少列 {missing}: {csv_path}")
        for row_number, row in enumerate(reader, start=2):
            ticker = (row.get("ticker") or "").strip()
            if not ticker:
                continue
            try:
                parsed = {
                    "ticker": ticker,
                    "date": parse_date(row.get("date")),
                    "close": parse_float(row.get("close")),
                }
            except ValueError as exc:
                raise RuntimeError(f"行情数据第 {row_number} 行格式错误: {exc}") from exc
            for column in ["open", "high", "low", "volume", "amount", "turnover"]:
                if column in row and str(row.get(column) or "").strip():
                    parsed[column] = parse_float(row.get(column))
            bars.append(parsed)

    return sorted(bars, key=lambda item: (item["ticker"], item["date"]))


def group_price_bars_by_ticker(bars):
    """Group price bars by ticker with chronological ordering."""
    grouped = defaultdict(list)
    for bar in bars:
        grouped[bar["ticker"]].append(bar)
    return {ticker: sorted(items, key=lambda item: item["date"]) for ticker, items in grouped.items()}


def parse_date(value):
    """Parse a CSV date value into a date object."""
    text = str(value or "").strip()
    if not text:
        raise ValueError("date 为空")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"无法解析日期 {text!r}") from exc


def parse_float(value):
    """Parse a numeric CSV value."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        raise ValueError("数值为空")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"无法解析数值 {text!r}") from exc

