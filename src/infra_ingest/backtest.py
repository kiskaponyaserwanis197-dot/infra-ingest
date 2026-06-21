"""Minimal event-study backtest utilities for text-derived research ideas."""

import json
from pathlib import Path

from .quant_data import group_price_bars_by_ticker, load_price_bars, parse_date


DEFAULT_EVENT_HORIZONS = (5, 20, 60)


def run_event_study(
    price_csv,
    tickers,
    *,
    event_date=None,
    horizons=DEFAULT_EVENT_HORIZONS,
    benchmark_ticker=None,
):
    """Run a forward-return event study from a price CSV.

    This is intentionally small: it validates whether an extracted text signal
    can be tied to prices at all. Heavier engines such as Qlib/vectorbt can
    replace this module once the research data contract is stable.
    """
    if not price_csv:
        return None

    tickers = [str(ticker).strip() for ticker in tickers or [] if str(ticker).strip()]
    if not tickers:
        return skipped_event_study("未识别到 ticker，无法把文本观点连接到行情数据。", event_date, horizons)
    if not event_date:
        return skipped_event_study("未提供 --event-date，已跳过前瞻收益事件研究。", event_date, horizons)

    bars = load_price_bars(price_csv)
    grouped = group_price_bars_by_ticker(bars)
    parsed_event_date = parse_date(event_date)
    benchmark_returns = {}
    warnings = []

    if benchmark_ticker:
        benchmark_returns = forward_returns_for_ticker(
            grouped.get(benchmark_ticker, []),
            parsed_event_date,
            horizons,
        )
        if not benchmark_returns:
            warnings.append(f"benchmark_ticker={benchmark_ticker} 没有足够行情数据。")

    observations = []
    for ticker in tickers:
        ticker_returns = forward_returns_for_ticker(grouped.get(ticker, []), parsed_event_date, horizons)
        if not ticker_returns:
            warnings.append(f"{ticker} 没有事件日或足够的前瞻行情。")
            continue
        for horizon, item in ticker_returns.items():
            benchmark_return = benchmark_returns.get(horizon, {}).get("return") if benchmark_returns else None
            excess_return = item["return"] - benchmark_return if benchmark_return is not None else None
            observations.append(
                {
                    "ticker": ticker,
                    "event_date": item["event_date"],
                    "event_close": item["event_close"],
                    "horizon_days": horizon,
                    "exit_date": item["exit_date"],
                    "exit_close": item["exit_close"],
                    "return": item["return"],
                    "benchmark_ticker": benchmark_ticker,
                    "benchmark_return": benchmark_return,
                    "excess_return": excess_return,
                }
            )

    if not observations:
        return {
            "type": "event_study",
            "status": "skipped",
            "event_date": parsed_event_date.isoformat(),
            "horizons": list(horizons),
            "tickers": tickers,
            "benchmark_ticker": benchmark_ticker,
            "reason": "没有可计算的事件研究样本。",
            "warnings": warnings,
            "observations": [],
            "summary": {},
        }

    return {
        "type": "event_study",
        "status": "ok",
        "event_date": parsed_event_date.isoformat(),
        "horizons": list(horizons),
        "tickers": tickers,
        "benchmark_ticker": benchmark_ticker,
        "warnings": warnings,
        "observations": observations,
        "summary": summarize_event_observations(observations),
    }


def forward_returns_for_ticker(bars, event_date, horizons):
    """Compute forward close-to-close returns from the latest bar <= event_date."""
    if not bars:
        return {}
    event_index = None
    for index, bar in enumerate(bars):
        if bar["date"] <= event_date:
            event_index = index
        else:
            break
    if event_index is None:
        return {}

    event_bar = bars[event_index]
    results = {}
    for horizon in horizons:
        exit_index = event_index + int(horizon)
        if exit_index >= len(bars):
            continue
        exit_bar = bars[exit_index]
        results[int(horizon)] = {
            "event_date": event_bar["date"].isoformat(),
            "event_close": event_bar["close"],
            "exit_date": exit_bar["date"].isoformat(),
            "exit_close": exit_bar["close"],
            "return": (exit_bar["close"] / event_bar["close"]) - 1,
        }
    return results


def summarize_event_observations(observations):
    """Summarize event-study observations by horizon."""
    summary = {}
    for horizon in sorted({item["horizon_days"] for item in observations}):
        rows = [item for item in observations if item["horizon_days"] == horizon]
        returns = [item["return"] for item in rows]
        excess_returns = [item["excess_return"] for item in rows if item["excess_return"] is not None]
        payload = {
            "sample_size": len(rows),
            "average_return": sum(returns) / len(returns),
            "hit_rate": sum(1 for value in returns if value > 0) / len(returns),
        }
        if excess_returns:
            payload["average_excess_return"] = sum(excess_returns) / len(excess_returns)
            payload["excess_hit_rate"] = sum(1 for value in excess_returns if value > 0) / len(excess_returns)
        summary[str(horizon)] = payload
    return summary


def skipped_event_study(reason, event_date, horizons):
    """Return a structured skipped event-study payload."""
    return {
        "type": "event_study",
        "status": "skipped",
        "event_date": event_date,
        "horizons": list(horizons),
        "tickers": [],
        "benchmark_ticker": None,
        "reason": reason,
        "warnings": [],
        "observations": [],
        "summary": {},
    }


def write_backtest_result(output_path, result):
    """Write a backtest JSON sidecar next to a generated note."""
    if not result:
        return None
    result_path = Path(output_path).with_suffix(".backtest.json")
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(result_path)

