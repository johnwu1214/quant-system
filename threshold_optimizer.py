#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
threshold_optimizer.py - pre_buy_checker 阈值回测优化
自动拉取 BaoStock 数据，测试不同阈值下的候选股分布
"""
import json, os, sys
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import baostock as bs

BASE_DIR     = Path(__file__).parent
DECISION_LOG = BASE_DIR / 'decision_log.jsonl'

sys.path.insert(0, str(BASE_DIR))
from pre_buy_checker import check_stock

def get_df_for_stock(symbol: str, days: int = 90) -> pd.DataFrame:
    """用 BaoStock 拉取单只股票历史日线，返回 pre_buy_checker 需要的 DataFrame"""
    end_date   = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')

    bs_code = f"sh.{symbol}" if symbol.startswith('6') else f"sz.{symbol}"
    rs = bs.query_history_k_data_plus(
        bs_code,
        'date,open,high,low,close,volume,amount,pctChg',
        start_date=start_date,
        end_date=end_date,
        frequency='d',
        adjustflag='3'
    )
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=['date','open','high','low','close','volume','amount','pctChg'])
    for col in ['open','high','low','close','volume','amount','pctChg']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close','volume'])
    df = df.set_index('date')
    return df


def load_decisions():
    records = []
    try:
        with open(DECISION_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    except FileNotFoundError:
        pass
    return records


def run_threshold_backtest():
    print("=" * 60)
    print("  pre_buy_checker 阈值回测优化器")
    print("=" * 60)

    # ── Step 1: 获取沪深300成分股 ──────────────────────────
    print("\n[1] 获取沪深300成分股...")
    bs.login()
    rs_cons = bs.query_hs300_stocks()
    stocks = []
    while rs_cons.error_code == '0' and rs_cons.next():
        row = rs_cons.get_row_data()
        code = row[1]  # 格式：sh.600000 或 sz.000001
        symbol = code.split('.')[-1]
        name   = row[2] if len(row) > 2 else symbol
        stocks.append((symbol, name))
    print(f"  获取到 {len(stocks)} 只成分股")

    # ── Step 2: 抽样50只，计算审查分数 ───────────────────────
    sample = stocks[:50]
    print(f"\n[2] 对前50只成分股计算审查分数...")
    print(f"  回测窗口: 最近90天")

    results = []
    errors  = 0
    for i, (symbol, name) in enumerate(sample):
        try:
            df = get_df_for_stock(symbol, days=90)
            if df.empty or len(df) < 20:
                errors += 1
                continue
            r = check_stock(symbol, name, df)
            if r and r.get('score') is not None:
                results.append(r)
        except Exception as e:
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"  已处理 {i+1}/50 只...")

    bs.logout()

    if not results:
        print("❌ 没有获取到有效结果，请检查数据源或 pre_buy_checker.py")
        return

    print(f"\n  有效结果: {len(results)} 只   跳过/错误: {errors} 只")

    # ── Step 3: 各阈值通过率分析 ──────────────────────────
    print("\n[3] 各阈值通过率分析")
    print("-" * 55)
    df_res = pd.DataFrame(results)
    scores = df_res['score'].tolist()
    print(f"  分数分布: min={min(scores):.0f}  max={max(scores):.0f}  "
          f"均值={np.mean(scores):.1f}  中位数={np.median(scores):.1f}\n")

    thresholds  = [40, 50, 55, 60, 65, 70, 75, 80]
    best_thresh = 60
    print(f"  {'阈值':>5}  {'通过数':>6}  {'通过率':>8}  建议")
    print(f"  {'─'*5}  {'─'*6}  {'─'*8}  {'─'*22}")
    for t in thresholds:
        n_pass = int((df_res['score'] >= t).sum())
        rate   = n_pass / len(df_res) * 100
        if 3 <= n_pass <= 12:
            tag = "← 推荐区间"
            best_thresh = t
        elif n_pass < 3:
            tag = "过严，候选太少"
        else:
            tag = "过宽，噪音较多"
        print(f"  {t:>5}  {n_pass:>6}  {rate:>7.1f}%  {tag}")

    # ── Step 4: 当前60分候选详情 ──────────────────────────
    print(f"\n[4] 当前阈值60分 候选股详情")
    print("-" * 55)
    passed = df_res[df_res['score'] >= 60].sort_values('score', ascending=False)
    if len(passed) == 0:
        print("  当前60分以上: 0只（市场偏弱，正常现象）")
    else:
        for _, row in passed.head(10).iterrows():
            d     = row.get('details', {})
            def _f(v):
                try: return float(v)
                except: return 0.0
            rsi   = _f(d.get('rsi', 0))   if isinstance(d, dict) else 0.0
            mb    = _f(d.get('macd_bar', 0)) if isinstance(d, dict) else 0.0
            turn  = _f(d.get('turnover', 0)) if isinstance(d, dict) else 0.0
            price = _f(d.get('current_price', 0)) if isinstance(d, dict) else 0.0
            print(f"  {row['symbol']}  {row['name']:<8}  {row['score']:>5.1f}分  "
                  f"RSI={rsi:.1f}  MACD柱={mb:.2f}  换手={turn:.1f}%  价={price:.2f}")

    # ── Step 5: 历史决策日志分析 ──────────────────────────
    print(f"\n[5] 历史决策日志分析")
    print("-" * 55)
    decisions = load_decisions()
    if not decisions:
        print("  decision_log.jsonl 暂无记录")
        print("  建议: 运行3-4周后再做阈值回测，样本量更充分")
    else:
        buys = [d for d in decisions if d.get('action') == 'buy']
        print(f"  历史决策总记录: {len(decisions)} 条")
        print(f"  买入决策:       {len(buys)} 条")

    # ── Step 6: 最终建议 ──────────────────────────────────
    n_curr = int((df_res['score'] >= 60).sum())
    n_best = int((df_res['score'] >= best_thresh).sum())

    print(f"\n[6] 优化建议")
    print("-" * 55)
    print(f"  当前阈值:  60分  → 通过 {n_curr} 只")
    print(f"  建议阈值:  {best_thresh}分  → 通过 {n_best} 只")

    if best_thresh == 60:
        print(f"  结论: ✅ 当前60分阈值合理，无需调整")
    elif best_thresh > 60:
        print(f"  结论: ⬆️  建议提高到{best_thresh}分，减少噪音")
    else:
        print(f"  结论: ⬇️  建议降低到{best_thresh}分，扩大候选池")

    print(f"\n  💡 当前市场震荡偏弱，候选股天然偏少")
    print(f"     牛市环境候选数 ×3～×5，届时可上调阈值至65-70")
    print(f"\n{'='*60}")
    print(f"  ✅ 阈值回测完成")
    print(f"{'='*60}")


if __name__ == '__main__':
    run_threshold_backtest()
