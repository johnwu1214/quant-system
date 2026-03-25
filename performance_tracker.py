#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
performance_tracker.py - 绩效统计模块
每日收盘后计算并保存绩效数据到 performance_log.jsonl
"""
import sys
import os
import json
import math
from datetime import datetime, date
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    import akshare as ak
except ImportError:
    ak = None

PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio_state.json")
DECISION_LOG   = os.path.join(BASE_DIR, "decision_log.jsonl")
PERF_LOG       = os.path.join(BASE_DIR, "performance_log.jsonl")
NAV_HISTORY    = os.path.join(BASE_DIR, "nav_history.jsonl")
INITIAL_NAV    = 100_000.0   # 初始净值基准10万

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"cash": 0, "positions": {}}

def load_decisions():
    """读取 decision_log.jsonl，返回已结束交易的盈亏记录"""
    records = []
    try:
        with open(DECISION_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        pass
    return records

def calc_drawdown(nav_series):
    """从净值序列计算最大回撤"""
    peak = nav_series[0]
    max_dd = 0.0
    for nav in nav_series:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)

def calc_sharpe(nav_series, periods_per_year=252):
    """计算夏普比率（简化版：年化收益/年化波动率）"""
    if len(nav_series) < 2:
        return 0.0
    # 计算日收益率
    returns = []
    for i in range(1, len(nav_series)):
        r = (nav_series[i] - nav_series[i-1]) / nav_series[i-1]
        returns.append(r)
    if not returns:
        return 0.0
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r)**2 for r in returns) / max(len(returns)-1, 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    annual_return = mean_r * periods_per_year
    annual_std = std * math.sqrt(periods_per_year)
    return round(annual_return / annual_std, 4)

def get_benchmark_return(target_date=None):
    """获取沪深300指定日期的涨跌幅"""
    if ak is None:
        return 0.0
    if target_date is None:
        target_date = date.today().strftime("%Y%m%d")
    try:
        df = ak.stock_zh_index_daily(symbol="sh000300")
        df = df[df['日期'].astype(str).str.replace('-','') <= target_date]
        if len(df) < 2:
            return 0.0
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        ret = (float(latest['收盘']) - float(prev['收盘'])) / float(prev['收盘'])
        return round(ret, 6)
    except Exception:
        return 0.0

def calc_performance(target_date=None):
    """计算绩效指标，返回摘要字典"""
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    decisions = load_decisions()
    state = load_portfolio()
    cash = state.get("cash", 0)
    positions = state.get("positions", {})

    # 计算持仓市值（用current_price）
    position_value = 0.0
    for code, pos in positions.items():
        shares = pos.get("shares", 0)
        price = pos.get("current_price", pos.get("cost", 0))
        position_value += shares * price

    total_assets = cash + position_value

    # 从 decision_log 提取已结算交易（SELL有result非pending）
    sell_records = [r for r in decisions if r.get("action") == "SELL" and r.get("result") != "pending"]
    win_trades  = [r for r in sell_records if (r.get("net_proceeds") or (r.get("amount", 0) - r.get("commission", 0))) > 0]
    lose_trades = [r for r in sell_records if (r.get("net_proceeds") or (r.get("amount", 0) - r.get("commission", 0))) <= 0]

    win_count = len(win_trades)
    lose_count = len(lose_trades)
    total_trades = win_count + lose_count
    win_rate = round(win_count / total_trades, 4) if total_trades > 0 else 0.0

    # 盈亏计算（用net_proceeds或旧amount）
    wins = []
    losses = []
    for r in sell_records:
        proceeds = r.get("net_proceeds")
        if proceeds is None:
            proceeds = r.get("amount", 0) - r.get("commission", 0) - r.get("tax", 0)
        cost = r.get("price", 0) * r.get("shares", 0)
        pnl = proceeds - cost
        if pnl > 0:
            wins.append(pnl)
        else:
            losses.append(pnl)

    avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0

    # 历史净值序列（从 performance_log 或推算）
    nav_series = []
    try:
        with open(PERF_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    nav_series.append(json.loads(line).get("nav", 1.0))
    except FileNotFoundError:
        nav_series = []

    current_nav = total_assets / INITIAL_NAV
    nav_series.append(current_nav)

    max_drawdown = calc_drawdown(nav_series)
    sharpe = calc_sharpe(nav_series)

    # 当日收益（从上一条净值推算）
    if len(nav_series) >= 2:
        daily_ret = round((current_nav / nav_series[-2]) - 1, 6)
    else:
        daily_ret = 0.0

    total_ret = round(current_nav - 1, 6)

    result = {
        "date": target_date,
        "nav": round(current_nav, 6),
        "total": round(total_assets, 2),
        "cash": round(cash, 2),
        "position_value": round(position_value, 2),
        "daily_pnl": round(total_assets - INITIAL_NAV * (nav_series[-2] if len(nav_series) >= 2 else 1.0), 2),
        "daily_ret": daily_ret,
        "total_ret": total_ret,
        "win_trades": win_count,
        "lose_trades": lose_count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "total_trades": total_trades
    }
    return result

def save_performance(result):
    """追加绩效到 performance_log.jsonl"""
    os.makedirs(os.path.dirname(PERF_LOG), exist_ok=True)
    with open(PERF_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

def append_nav_history(target_date=None):
    """追加净值历史（含基准）- 同一天只保留最新一条，避免重复脏数据"""
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")
    perf = calc_performance(target_date)
    nav  = perf["nav"]
    total_assets = perf.get("total_assets", round(nav * INITIAL_NAV, 2))
    benchmark = get_benchmark_return()

    # ── 读取现有记录，计算累计基准净值 ──────────────────────
    existing = {}
    try:
        with open(NAV_HISTORY, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if 'date' in rec and 'nav' in rec:
                        existing[rec['date']] = rec
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    # 取上一条记录的 benchmark_nav 作为基准
    last_bench_nav = 1.0
    sorted_dates = sorted(existing.keys())
    for d in reversed(sorted_dates):
        if d < target_date:
            last_bench_nav = existing[d].get("benchmark_nav", 1.0)
            break
    bench_nav = round(last_bench_nav * (1 + benchmark), 6)
    excess    = round(nav - bench_nav, 6)

    nav_record = {
        "date":          target_date,
        "nav":           nav,
        "total_assets":  total_assets,
        "benchmark":     benchmark,
        "benchmark_nav": bench_nav,
        "excess":        excess
    }

    # ── 覆盖当天记录，保持文件干净 ──────────────────────────
    existing[target_date] = nav_record
    sorted_records = [existing[d] for d in sorted(existing.keys())]
    with open(NAV_HISTORY, 'w', encoding='utf-8') as f:
        for rec in sorted_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return nav_record

def get_summary():
    """返回当前绩效摘要"""
    return calc_performance()

def get_perf_history(days=30):
    """读取最近N条绩效记录"""
    records = []
    try:
        with open(PERF_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        return []
    return records[-days:]

def get_nav_history(days=30):
    """读取最近N条净值历史"""
    records = []
    try:
        with open(NAV_HISTORY, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        return []
    return records[-days:]

# ── CLI 入口 ──────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily", action="store_true", help="收盘绩效计算+保存")
    parser.add_argument("--open-snapshot", action="store_true", help="开盘快照")
    args = parser.parse_args()

    if args.daily or len(sys.argv) == 1:
        result = calc_performance()
        save_performance(result)
        append_nav_history()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("绩效已保存到 performance_log.jsonl")
    else:
        result = get_summary()
        print(json.dumps(result, ensure_ascii=False, indent=2))
