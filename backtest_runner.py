#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_runner.py - 策略回测入口
读取trading_config参数，回测2023-01-01~2026-03-01，输出报告+微信推送
"""
import sys
import os
import json
import math
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    import akshare as ak
    import pandas as pd
    import numpy as np
except ImportError:
    print("缺少依赖: pip install akshare pandas numpy")
    sys.exit(1)

from intraday_v4_2 import calculate_trade_cost

CONFIG_FILE  = os.path.join(BASE_DIR, "trading_config.json")
RESULT_FILE  = os.path.join(BASE_DIR, "backtest_result.json")

# ── 读取配置 ──────────────────────────────────────────
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ── 获取历史日线数据 ────────────────────────────────────
def code_to_qlib(code):
    """将股票代码转换为 Qlib 格式: 600036 → sh600036"""
    code = str(code).strip()
    if code.startswith(('sh', 'sz')):
        return code
    if code.startswith(('6', '9')):
        return f'sh{code}'
    return f'sz{code}'

# 初始化 Qlib（只初始化一次）
_qlib_inited = False
def _init_qlib():
    global _qlib_inited
    if not _qlib_inited:
        import qlib
        qlib.init(provider_uri='/root/qlib_data/cn_data_community', region='cn')
        _qlib_inited = True

def get_history(code, start, end):
    """用 Qlib 本地数据获取历史日线（离线，无需网络）"""
    try:
        _init_qlib()
        from qlib.data import D
        qlib_code = code_to_qlib(code)
        # 格式化日期
        if len(start) == 8:
            start = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        if len(end) == 8:
            end = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        df = D.features(
            [qlib_code],
            ['$open', '$high', '$low', '$close', '$volume'],
            start_time=start,
            end_time=end
        )
        if df.empty:
            return pd.DataFrame()
        # 重置索引，统一列名
        df = df.reset_index()
        df.columns = ['instrument', 'date', 'open', 'high', 'low', 'close', 'volume']
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        df = df[['open', 'high', 'low', 'close', 'volume']]
        return df
    except Exception as e:
        print(f"获取 {code} 数据失败: {e}")
        return pd.DataFrame()

# ── 四因子选股信号 ─────────────────────────────────────
def factor_signal(df, lookback=60):
    """简化四因子：动量+量价+RSI+MA趋势"""
    if len(df) < lookback:
        return None
    recent = df.tail(lookback)
    close = df['close']

    # 动量：20日收益率 > 0
    momentum = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0

    # 量价：成交量高于20日均量
    vol_ma = df['volume'].rolling(20).mean()
    vol_ratio = df['volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] > 0 else 0

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1]

    # MA趋势：现价 > MA60
    ma60 = close.rolling(60).mean()
    above_ma = 1 if close.iloc[-1] > ma60.iloc[-1] else 0

    score = 0
    if momentum > 0: score += 25
    if vol_ratio > 1.2: score += 25
    if 40 < rsi_val < 70: score += 25
    if above_ma: score += 25

    return score

# ── ATR 计算 ───────────────────────────────────────────
def calc_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr.iloc[-1] if len(atr) > 0 else 0

# ── 回测主循环 ─────────────────────────────────────────
def run_backtest(codes, start_date, end_date, config):
    INITIAL = 100_000.0
    cash = INITIAL
    positions = {}  # {code: {'shares', 'cost', 'atr', 'entry_price'}}
    trades = []
    nav_series = []

    dates = pd.date_range(start_date, end_date, freq='B')  # 工作日

    for today in dates:
        # 计算当前总市值
        pos_value = sum(s['shares'] * s['cost'] for s in positions.values())
        total = cash + pos_value
        nav_series.append({'date': today.strftime('%Y-%m-%d'), 'nav': total / INITIAL})

        # 读取各标的当日数据（使用最近可用日线）
        signals = {}
        for code in codes:
            df = get_history(code, start_date, today.strftime('%Y%m%d'))
            if df.empty or len(df) < 60:
                continue
            score = factor_signal(df)
            if score is not None:
                signals[code] = {
                    'score': score,
                    'close': df['close'].iloc[-1],
                    'atr': calc_atr(df)
                }

        # 买入信号
        buy_threshold = config.get('BUY_THRESHOLD', 75)
        max_pos = config.get('MAX_POSITIONS', 5)
        pos_ratio = config.get('MAX_POSITION_RATIO', 0.65)

        for code, sig in sorted(signals.items(), key=lambda x: -x[1]['score']):
            if len(positions) >= max_pos:
                break
            if code in positions:
                continue
            if sig['score'] < buy_threshold:
                continue

            # 分配仓位
            size_map = config.get('POSITION_SIZES', {})
            if sig['score'] >= 90:
                size_ratio = size_map.get('HIGH', 0.15)
            elif sig['score'] >= 75:
                size_ratio = size_map.get('MEDIUM', 0.08)
            else:
                size_ratio = size_map.get('LOW', 0.04)

            alloc = total * size_ratio
            price = sig['close']
            shares = int(alloc / price / 100) * 100  # 整手

            if shares < 100:
                continue

            cost_info = calculate_trade_cost("BUY", price, shares)
            total_cost = shares * cost_info['actual_price'] + cost_info['commission']

            if cash < total_cost:
                continue

            cash -= total_cost
            positions[code] = {
                'shares': shares,
                'cost': cost_info['actual_price'],
                'atr': sig['atr'],
                'entry_price': price,
                'entry_date': today.strftime('%Y-%m-%d')
            }
            trades.append({
                'date': today.strftime('%Y-%m-%d'),
                'action': 'BUY',
                'code': code,
                'price': price,
                'shares': shares,
                'commission': cost_info['commission']
            })

        # 卖出信号
        sell_threshold = config.get('SELL_THRESHOLD', 40)
        hard_stop = config.get('HARD_STOP_LOSS', -0.08)
        atr_mult = config.get('STOP_LOSS_ATR_MULTIPLIER', 3.0)

        for code in list(positions.keys()):
            df = get_history(code, start_date, today.strftime('%Y%m%d'))
            if df.empty:
                continue
            current_price = df['close'].iloc[-1]
            entry = positions[code]
            pnl_pct = (current_price - entry['cost']) / entry['cost']
            atr_stop = entry['atr'] / entry['cost'] * atr_mult

            should_sell = False
            reason = ""

            # 技术信号转弱
            sig = signals.get(code, {'score': 0})
            if sig['score'] < sell_threshold:
                should_sell = True
                reason = f"信号减弱({sig['score']})"
            # 硬止损
            elif pnl_pct < hard_stop:
                should_sell = True
                reason = f"硬止损({pnl_pct:.1%})"
            # ATR跟踪止损
            elif pnl_pct < -atr_stop:
                should_sell = True
                reason = f"ATR止损({pnl_pct:.1%})"

            if should_sell:
                cost_info = calculate_trade_cost("SELL", current_price, entry['shares'])
                net = entry['shares'] * cost_info['actual_price'] - cost_info['commission'] - cost_info['tax']
                pnl = net - entry['shares'] * entry['cost']
                cash += net
                trades.append({
                    'date': today.strftime('%Y-%m-%d'),
                    'action': 'SELL',
                    'code': code,
                    'price': current_price,
                    'shares': entry['shares'],
                    'commission': cost_info['commission'],
                    'tax': cost_info['tax'],
                    'pnl': round(pnl, 2)
                })
                del positions[code]

    # 最终结算
    pos_value = sum(s['shares'] * s['cost'] for s in positions.values())
    final_total = cash + pos_value
    nav_series.append({'date': end_date, 'nav': final_total / INITIAL})

    return {
        'trades': trades,
        'nav_series': nav_series,
        'final_total': final_total,
        'initial': INITIAL,
        'period': f"{start_date}~{end_date}"
    }

# ── 绩效统计 ───────────────────────────────────────────
def calc_stats(result, benchmark_return):
    trades = result['trades']
    nav_series = result['nav_series']
    final_nav = result['nav_series'][-1]['nav']

    # 年化收益
    start = datetime.strptime(result['period'].split('~')[0], '%Y-%m-%d')
    end = datetime.strptime(result['period'].split('~')[1], '%Y-%m-%d')
    years = (end - start).days / 365.25
    annual_return = round((final_nav ** (1 / years) - 1), 4) if years > 0 else 0

    # 最大回撤
    peak = nav_series[0]['nav']
    max_dd = 0.0
    for entry in nav_series:
        nav = entry['nav']
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普比率（简化）
    returns = []
    for i in range(1, len(nav_series)):
        r = (nav_series[i]['nav'] - nav_series[i-1]['nav']) / nav_series[i-1]['nav']
        returns.append(r)
    if returns:
        mean_r = sum(returns) / len(returns)
        std = math.sqrt(sum((r-mean_r)**2 for r in returns) / max(len(returns)-1,1))
        sharpe = round(mean_r / std * math.sqrt(252), 4) if std > 0 else 0
    else:
        sharpe = 0

    # 胜率
    sells = [t for t in trades if t['action'] == 'SELL' and 'pnl' in t]
    wins = [t for t in sells if t['pnl'] > 0]
    win_rate = round(len(wins) / len(sells), 4) if sells else 0

    return {
        "period": result['period'],
        "annual_return": annual_return,
        "max_drawdown": round(max_dd, 4),
        "sharpe": sharpe,
        "win_rate": win_rate,
        "total_trades": len(trades),
        "buy_trades": len([t for t in trades if t['action'] == 'BUY']),
        "sell_trades": len(sells),
        "benchmark_return": round(benchmark_return, 4),
        "final_nav": round(final_nav, 6),
        "total_return": round(final_nav - 1, 6)
    }

# ── 主入口 ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 40)
    print("策略回测启动")
    print("=" * 40)

    config = load_config()
    print(f"配置: BUY={config['BUY_THRESHOLD']} SELL={config['SELL_THRESHOLD']} MAX={config['MAX_POSITIONS']}")

    # 读取监控池作为回测标的
    import json as _json
    WATCH_FILE = os.path.join(BASE_DIR, "watch_list.json")
    try:
        with open(WATCH_FILE, 'r') as f:
            watch_data = _json.load(f)
        # watch_list.json 顶层是 dict，stocks 在 "stocks" 键下
        if isinstance(watch_data, dict):
            stocks = watch_data.get('stocks', [])
        elif isinstance(watch_data, list):
            stocks = watch_data
        else:
            stocks = []

        if stocks and isinstance(stocks[0], dict):
            codes = [s.get('symbol') or s.get('code') for s in stocks
                     if s.get('symbol') or s.get('code')]
        else:
            codes = [str(s) for s in stocks if s]
    except Exception:
        codes = ['000001', '000002', '600036', '600519', '601318',
                 '000858', '600276', '601888', '300750', '002594']

    START = "20240101"
    END   = "20260301"

    print(f"回测期间: {START} ~ {END}")
    print(f"标的数量: {len(codes)}")
    print("正在回测，请稍候...")

    # 基准收益：用 Qlib 本地数据读沪深300
    try:
        from backtest_runner import get_history
        df_bench = get_history('000300', START, END)
        if len(df_bench) >= 2:
            bench_ret = (df_bench['close'].iloc[-1] - df_bench['close'].iloc[0]) / df_bench['close'].iloc[0]
            bench_ret = round(float(bench_ret), 4)
            print(f"基准收益(沪深300): {bench_ret*100:.1f}%")
        else:
            bench_ret = 0.08
    except Exception as e:
        print(f"基准收益获取失败({e})，使用默认值8%")
        bench_ret = 0.08

    result = run_backtest(codes, START, END, config)
    stats = calc_stats(result, bench_ret)

    # 保存结果
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        _json.dump(stats, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 40)
    print("回测报告")
    print("=" * 40)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # 微信推送
    try:
        from weixin_notify import send_weixin
        msg = (
            f"📊 回测报告\n"
            f"━━━━━━━━━━━━\n"
            f"期间：{stats['period']}\n"
            f"年化收益：{stats['annual_return']*100:.1f}%\n"
            f"最大回撤：{stats['max_drawdown']*100:.1f}%\n"
            f"夏普比率：{stats['sharpe']:.2f}\n"
            f"胜率：{stats['win_rate']*100:.0f}%\n"
            f"总交易：{stats['total_trades']}笔\n"
            f"基准收益：{stats['benchmark_return']*100:.1f}%\n"
            f"超额收益：{(stats['annual_return']-stats['benchmark_return'])*100:+.1f}%\n"
            f"━━━━━━━━━━━━\n"
            f"✅ 报告已保存"
        )
        send_weixin(msg)
        print("\n微信推送已发送")
    except Exception as e:
        print(f"\n微信推送失败: {e}")

    print(f"\n结果已保存到 {RESULT_FILE}")
