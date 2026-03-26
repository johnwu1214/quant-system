#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
买入前深度审查模块 pre_buy_checker.py
=====================================
设计原则（基于研究）：
  1. 三重滤网：趋势层 → 动量层 → 量能层，层层过滤
  2. 只买支撑，不追阻力（Only buy support, never buy resistance）
  3. RSI超卖必须有量能配合，缩量超卖=下跌陷阱
  4. 综合评分制：每项检查给分，总分决定是否通过

评分体系（满分100分，>=60分通过）：
  趋势层（40分）
    - MA5 > MA20（短期均线多头）         +15
    - 价格 > MA20（站上中期均线）         +15
    - 距历史高点回撤 < 20%               +10
  动量层（35分）
    - RSI 30~70 健康区间                 +15
    - RSI从底部回升（非持续下跌）         +10
    - MACD金叉或DIF>0                   +10
  量能层（25分）
    - 量比 >= 0.8（成交活跃）             +10
    - 近5日成交额持续放量（上升趋势）      +10
    - 换手率 1%~15%（合理范围）           +5

拒绝条件（一票否决，直接不通过）：
  - 死叉且RSI<25且量比<0.6（缩量阴跌陷阱）
  - 20日内跌幅>25%（急跌不抄底）
  - 成交量连续5日萎缩且价格下跌
  - 价格连续创新低（下跌趋势未止）

作者：quant-system
更新：2026-03-25
"""

import sys
import json
import warnings
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.WARNING)

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# ── 技术指标计算 ──────────────────────────────────────────

def calc_rsi(prices: np.ndarray, period: int = 14) -> float:
    """计算RSI"""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)

def calc_macd(prices: np.ndarray, fast=12, slow=26, signal=9):
    """计算MACD，返回(DIF, DEA, MACD柱)"""
    if len(prices) < slow + signal:
        return 0.0, 0.0, 0.0
    s = pd.Series(prices)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return float(dif.iloc[-1]), float(dea.iloc[-1]), float(macd.iloc[-1])

def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    """计算ATR"""
    try:
        high  = df['high'].astype(float).values if 'high' in df.columns else None
        low   = df['low'].astype(float).values  if 'low'  in df.columns else None
        close = df['close'].astype(float).values
        if high is None or low is None:
            return float(np.std(np.diff(close[-period:])))
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:]  - close[:-1])
            )
        )
        return float(np.mean(tr[-period:]))
    except Exception:
        return 0.0

# ── 核心审查函数 ──────────────────────────────────────────

def check_stock(symbol: str, name: str, df: pd.DataFrame) -> dict:
    """
    对单只股票进行买入前深度审查

    参数：
        symbol: 股票代码（6位）
        name:   股票名称
        df:     历史日线数据（至少60行），需含 close/volume/amount 列

    返回：
        {
            'symbol':   '601808',
            'name':     '中海油服',
            'passed':   False,
            'score':    38,
            'verdict':  '❌ 拒绝',
            'reason':   '一票否决：缩量阴跌陷阱',
            'details':  {...}  # 各指标详情
        }
    """
    result = {
        'symbol':  symbol,
        'name':    name,
        'passed':  False,
        'score':   0,
        'verdict': '',
        'reason':  '',
        'details': {},
        'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # ── 数据准备 ──
    if df is None or len(df) < 20:
        result['verdict'] = '❌ 数据不足'
        result['reason']  = f'历史数据仅{len(df) if df is not None else 0}条，需要至少20条'
        return result

    df = df.copy().sort_index()
    close  = df['close'].astype(float).values
    volume = df['volume'].astype(float).values if 'volume' in df.columns else np.ones(len(df))
    amount = df['amount'].astype(float).values if 'amount' in df.columns else np.zeros(len(df))

    current = close[-1]
    n       = len(close)

    # ── 基础指标计算 ──
    ma5   = float(np.mean(close[-5:]))   if n >= 5  else current
    ma10  = float(np.mean(close[-10:]))  if n >= 10 else current
    ma20  = float(np.mean(close[-20:]))  if n >= 20 else current
    ma60  = float(np.mean(close[-60:]))  if n >= 60 else current

    rsi        = calc_rsi(close)
    rsi_5d_ago = calc_rsi(close[:-5]) if n > 19 else rsi
    dif, dea, macd_bar = calc_macd(close)

    # 量能指标
    vol_ma5  = float(np.mean(volume[-5:]))   if n >= 5  else float(volume[-1])
    vol_ma20 = float(np.mean(volume[-20:]))  if n >= 20 else float(volume[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0  # 量比（5日均量/20日均量）

    # 成交额（万元）
    avg_amount_5d = float(np.mean(amount[-5:])) / 1e4 if np.any(amount > 0) else 0

    # 换手率（如果有）
    turnover = float(df['turn'].astype(float).mean()) if 'turn' in df.columns and df['turn'].astype(str).str.strip().ne('').any() else -1

    # 回撤与趋势
    high_60d   = float(np.max(close[-60:])) if n >= 60 else float(np.max(close))
    low_60d    = float(np.min(close[-60:])) if n >= 60 else float(np.min(close))
    drawdown   = (current / high_60d - 1) * 100   # 负数，如 -20.9%
    rebound    = (current / low_60d  - 1) * 100   # 正数，如 +5.8%

    # 20日涨跌幅
    ret_20d = (current / close[-20] - 1) * 100 if n >= 20 else 0.0

    # 是否连续创新低（近5日）
    is_making_new_lows = all(close[-5+i] <= close[-5+i-1] for i in range(1, 5)) if n >= 6 else False

    # 成交量是否连续萎缩（近5日）
    is_vol_shrinking = all(volume[-5+i] <= volume[-5+i-1] for i in range(1, 5)) if n >= 6 else False

    details = {
        'current_price': round(current, 2),
        'ma5':           round(ma5, 2),
        'ma10':          round(ma10, 2),
        'ma20':          round(ma20, 2),
        'ma60':          round(ma60, 2),
        'rsi':           rsi,
        'rsi_5d_ago':    rsi_5d_ago,
        'dif':           round(dif, 4),
        'dea':           round(dea, 4),
        'macd_bar':      round(macd_bar, 4),
        'vol_ratio':     round(vol_ratio, 2),
        'drawdown_pct':  round(drawdown, 1),
        'rebound_pct':   round(rebound, 1),
        'ret_20d_pct':   round(ret_20d, 1),
        'avg_amount_5d_wan': round(avg_amount_5d, 0),
        'turnover':      round(turnover, 2) if turnover > 0 else 'N/A',
        'is_making_new_lows':  is_making_new_lows,
        'is_vol_shrinking':    is_vol_shrinking,
    }
    result['details'] = details

    # ══════════════════════════════════════════
    # 一票否决条件（满足任一直接拒绝）
    # ══════════════════════════════════════════
    veto_reasons = []

    # 否决1：缩量阴跌陷阱（死叉 + RSI极低 + 缩量）
    if ma5 < ma20 and rsi < 25 and vol_ratio < 0.6:
        veto_reasons.append(f'缩量阴跌陷阱(MA死叉+RSI={rsi}+量比={vol_ratio:.2f})')

    # 否决2：20日急跌超25%
    if ret_20d < -25:
        veto_reasons.append(f'20日急跌{ret_20d:.1f}%，不抄底')

    # 否决3：连续5日创新低且成交量萎缩
    if is_making_new_lows and is_vol_shrinking:
        veto_reasons.append('连续5日创新低+缩量，下跌趋势未止')

    # 否决4：距高点回撤超30%且量比<0.7（长期弱势股）
    if drawdown < -30 and vol_ratio < 0.7:
        veto_reasons.append(f'距高点回撤{drawdown:.1f}%且量比{vol_ratio:.2f}，长期弱势')

    if veto_reasons:
        result['passed']  = False
        result['score']   = 0
        result['verdict'] = '❌ 一票否决'
        result['reason']  = ' | '.join(veto_reasons)
        return result

    # ══════════════════════════════════════════
    # 评分体系（满分100分）
    # ══════════════════════════════════════════
    score = 0
    score_log = []

    # ── 趋势层（40分）──
    # MA5 > MA20（短期多头排列）
    if ma5 > ma20:
        score += 15
        score_log.append('趋势:MA多头+15')
    else:
        score_log.append('趋势:MA死叉+0')

    # 价格站上MA20
    if current > ma20:
        score += 15
        score_log.append('价格>MA20+15')
    elif current > ma20 * 0.97:  # 接近MA20，给部分分
        score += 8
        score_log.append('价格接近MA20+8')
    else:
        score_log.append('价格<MA20+0')

    # 距高点回撤位置（越浅越好）
    if drawdown > -10:
        score += 10
        score_log.append(f'回撤{drawdown:.1f}%<10%+10')
    elif drawdown > -20:
        score += 6
        score_log.append(f'回撤{drawdown:.1f}%<20%+6')
    elif drawdown > -30:
        score += 3
        score_log.append(f'回撤{drawdown:.1f}%<30%+3')
    else:
        score_log.append(f'回撤{drawdown:.1f}%>30%+0')

    # ── 动量层（35分）──
    # RSI健康区间（30~70为有效信号）
    if 30 <= rsi <= 70:
        score += 15
        score_log.append(f'RSI={rsi}健康+15')
    elif 25 <= rsi < 30:
        score += 8  # 超卖边缘，减分
        score_log.append(f'RSI={rsi}超卖边缘+8')
    elif rsi > 70:
        score += 5  # 超买，风险较高
        score_log.append(f'RSI={rsi}超买风险+5')
    else:
        score_log.append(f'RSI={rsi}极端超卖+0')

    # RSI从底部回升（而非持续下跌）
    if rsi > rsi_5d_ago + 3:
        score += 10
        score_log.append(f'RSI回升{rsi-rsi_5d_ago:.1f}pts+10')
    elif rsi >= rsi_5d_ago:
        score += 5
        score_log.append('RSI企稳+5')
    else:
        score_log.append(f'RSI持续下跌-{rsi_5d_ago-rsi:.1f}pts+0')

    # MACD金叉或DIF>0
    if dif > dea and macd_bar > 0:
        score += 10
        score_log.append('MACD金叉+10')
    elif dif > dea:
        score += 6
        score_log.append('DIF>DEA+6')
    elif dif > 0:
        score += 3
        score_log.append('DIF>0+3')
    else:
        score_log.append('MACD死叉+0')

    # ── 量能层（25分）──
    # 量比（5日均量/20日均量）
    if vol_ratio >= 1.2:
        score += 10
        score_log.append(f'量比{vol_ratio:.2f}放量+10')
    elif vol_ratio >= 0.8:
        score += 6
        score_log.append(f'量比{vol_ratio:.2f}正常+6')
    elif vol_ratio >= 0.6:
        score += 2
        score_log.append(f'量比{vol_ratio:.2f}偏低+2')
    else:
        score_log.append(f'量比{vol_ratio:.2f}严重萎缩+0')

    # 近5日成交额趋势（是否在放量）
    if n >= 10:
        amt_5d  = float(np.mean(amount[-5:]))
        amt_10d = float(np.mean(amount[-10:-5]))
        if amt_10d > 0 and amt_5d > amt_10d * 1.1:
            score += 10
            score_log.append('近5日成交额放量+10')
        elif amt_10d > 0 and amt_5d >= amt_10d * 0.9:
            score += 5
            score_log.append('近5日成交额持平+5')
        else:
            score_log.append('近5日成交额萎缩+0')

    # 换手率合理范围
    if turnover > 0:
        if 1.0 <= turnover <= 15.0:
            score += 5
            score_log.append(f'换手率{turnover:.1f}%合理+5')
        elif turnover > 15:
            score += 2
            score_log.append(f'换手率{turnover:.1f}%偏高+2')
        else:
            score_log.append(f'换手率{turnover:.1f}%过低+0')
    else:
        # 没有换手率数据，用成交额估算
        if avg_amount_5d >= 3000:  # 日均成交额3000万以上
            score += 5
            score_log.append(f'日均成交额{avg_amount_5d:.0f}万+5')
        elif avg_amount_5d >= 1000:
            score += 3
            score_log.append(f'日均成交额{avg_amount_5d:.0f}万+3')

    result['score']    = score
    result['score_log'] = score_log

    # ── 最终判决 ──
    if score >= 65:
        result['passed']  = True
        result['verdict'] = '✅ 强烈推荐'
        result['reason']  = f'综合评分{score}/100，各维度信号良好'
    elif score >= 50:
        result['passed']  = True
        result['verdict'] = '✅ 可以买入'
        result['reason']  = f'综合评分{score}/100，基本面向好'
    elif score >= 35:
        result['passed']  = False
        result['verdict'] = '⚠️ 观望等待'
        result['reason']  = f'综合评分{score}/100，信号不够强，建议等待'
    else:
        result['passed']  = False
        result['verdict'] = '❌ 拒绝买入'
        result['reason']  = f'综合评分{score}/100，多项指标不达标'

    return result


# ── 批量审查入口 ──────────────────────────────────────────

def check_candidates(candidates: list, verbose: bool = True, threshold: int = 60) -> list:
    """
    批量审查候选股列表

    参数：
        candidates: [{'symbol':'601808','name':'中海油服',...}, ...]
                    需要包含 symbol 和 name 字段
        verbose:    是否打印详细输出

    返回：
        审查结果列表，按评分降序排列
    """
    import baostock as bs

    results = []
    passed  = []
    rejected = []

    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    if verbose:
        print(f'\n{"="*60}')
        print(f'🔍 买入前深度审查  {datetime.now().strftime("%H:%M:%S")}')
        print(f'   候选股数量: {len(candidates)} 只')
        print(f'{"="*60}')

    bs.login()

    for c in candidates:
        symbol = c.get('symbol') or c.get('code', '')
        name   = c.get('name', symbol)

        # 拉取历史日线
        bs_code = ('sh.' if symbol.startswith('6') else 'sz.') + symbol
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,open,high,low,close,volume,amount,turn,pctChg',
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag='3'
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            if verbose:
                print(f'  ⚠️  {symbol} {name}: 无数据，跳过')
            continue

        df = pd.DataFrame(rows, columns=rs.fields)
        df = df[df['close'] != ''].copy()
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['close'])
        df.set_index('date', inplace=True)

        # 执行审查
        r = check_stock(symbol, name, df)

        # 合并选股得分
        r['selector_score'] = c.get('score', 0)
        r['selector_reason'] = c.get('reason', '')

        results.append(r)

        if verbose:
            icon = '✅' if r['passed'] else ('⚠️' if r['score'] >= 35 else '❌')
            det  = r['details']
            print(f"\n  {icon} {symbol} {name}")
            print(f"     审查评分: {r['score']}/100  → {r['verdict']}")
            print(f"     价格:{det['current_price']}  MA5:{det['ma5']}  MA20:{det['ma20']}")
            print(f"     RSI:{det['rsi']}  量比:{det['vol_ratio']}  "
                  f"回撤:{det['drawdown_pct']}%  20日:{det['ret_20d_pct']}%")
            print(f"     结论: {r['reason']}")
            if 'score_log' in r:
                print(f"     评分明细: {' | '.join(r['score_log'])}")

        if r['passed']:
            passed.append(r)
        else:
            rejected.append(r)

    bs.logout()

    # 按审查评分排序
    results.sort(key=lambda x: x['score'], reverse=True)
    passed.sort(key=lambda x: x['score'],  reverse=True)

    if verbose:
        print(f'\n{"="*60}')
        print(f'📊 审查结果汇总')
        print(f'   候选: {len(results)} 只  通过: {len(passed)} 只  '
              f'拒绝: {len(rejected)} 只')
        print(f'{"="*60}')
        if passed:
            print('✅ 通过审查（建议买入）:')
            for r in passed:
                print(f"   {r['symbol']} {r['name']}  "
                      f"审查:{r['score']}分  {r['verdict']}")
        if rejected:
            print('❌ 未通过审查:')
            for r in rejected[:5]:  # 只显示前5个
                print(f"   {r['symbol']} {r['name']}  "
                      f"审查:{r['score']}分  {r['reason'][:40]}")

    return results


# ── 与 watch_list.json 集成 ──────────────────────────────

def check_watch_list(watch_file: str = None) -> list:
    """
    读取 watch_list.json，对其中候选股进行审查
    审查结果写回 watch_list.json（新增 check_result 字段）
    """
    if watch_file is None:
        watch_file = str(BASE_DIR / 'watch_list.json')

    with open(watch_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks = data.get('stocks', [])
    if not stocks:
        print('watch_list.json 为空')
        return []

    # 执行审查
    results = check_candidates(stocks, verbose=True)

    # 写回（只保留通过审查的股票，未通过的加标注）
    passed_symbols = {r['symbol'] for r in results if r['passed']}

    for s in stocks:
        sym = s.get('symbol') or s.get('code', '')
        match = next((r for r in results if r['symbol'] == sym), None)
        if match:
            s['check_score']   = match['score']
            s['check_verdict'] = match['verdict']
            s['check_reason']  = match['reason']
            s['check_passed']  = match['passed']
            s['check_details'] = match['details']
            s['checked_at']    = match['checked_at']

    data['checked_at']    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['passed_count']  = len(passed_symbols)
    data['total_checked'] = len(results)

    with open(watch_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 审查结果已写入 {watch_file}')
    return [r for r in results if r['passed']]


# ── 命令行入口 ────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='买入前深度审查')
    parser.add_argument('--symbol', type=str, help='指定单只股票代码，如 601808')
    parser.add_argument('--watch',  action='store_true', help='审查 watch_list.json 中所有候选股')
    args = parser.parse_args()

    if args.symbol:
        # 单只股票快速审查
        import baostock as bs
        bs.login()
        bs_code = ('sh.' if args.symbol.startswith('6') else 'sz.') + args.symbol
        end_date   = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,open,high,low,close,volume,amount,turn,pctChg',
            start_date=start_date, end_date=end_date,
            frequency='d', adjustflag='3'
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()

        if rows:
            df = pd.DataFrame(rows, columns=rs.fields)
            df = df[df['close'] != ''].copy()
            for col in ['open','high','low','close','volume','amount','turn','pctChg']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df.set_index('date', inplace=True)
            r = check_stock(args.symbol, args.symbol, df)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f'❌ 无法获取 {args.symbol} 的数据')

    elif args.watch:
        check_watch_list()

    else:
        # 默认：审查 watch_list.json
        check_watch_list()
