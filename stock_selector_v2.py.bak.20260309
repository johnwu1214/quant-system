#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能选股系统 v2.0
三模式自适应：牛市趋势追踪 / 震荡超卖反弹 / 熊市防御
数据源：Tushare
每日15:05收盘后自动运行
"""
import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import warnings
warnings.filterwarnings('ignore')

# ── 读取配置 ──
with open('config.json', 'r') as f:
    config = json.load(f)

ts.set_token(config['tushare_token'])
pro = ts.pro_api()

# ── 选股参数 ──
TOP_N = 10  # 最终选出数量
MIN_TRADE_DAYS = 60  # 最少上市交易天数
MIN_AMOUNT = 3000  # 日均成交额下限（万元）
WATCH_FILE = "watch_list.json"


# ════════════════════════════════════════
# 第一模块：技术指标计算
# ════════════════════════════════════════

def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(np.array(prices, dtype=float)[-(period+1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g, avg_l = gains.mean(), losses.mean()
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 1)


def calc_ema(prices, period):
    prices = np.array(prices, dtype=float)
    if len(prices) < period:
        return float(prices[-1])
    k = 2.0 / (period + 1)
    ema = float(prices[-period])
    for p in prices[-period+1:]:
        ema = p * k + ema * (1 - k)
    return ema


def calc_macd_diff(prices):
    if len(prices) < 26:
        return 0.0
    return calc_ema(prices, 12) - calc_ema(prices, 26)


def calc_momentum(prices, period=20):
    """N日价格动量"""
    if len(prices) < period + 1:
        return 0.0
    return (prices[-1] - prices[-period-1]) / prices[-period-1]


def calc_volatility(prices, period=20):
    """N日年化波动率"""
    if len(prices) < period + 1:
        return 0.0
    returns = np.diff(np.log(np.array(prices[-period-1:], dtype=float)))
    return round(returns.std() * np.sqrt(252), 4)


# ════════════════════════════════════════
# 第二模块：市场环境检测
# ════════════════════════════════════════

def detect_market_regime():
    """
    检测当前市场环境
    返回：'bull'（牛市）/ 'neutral'（震荡）/ 'bear'（熊市）
    """
    import baostock as bs
    import numpy as np
    from datetime import datetime, timedelta
    try:
        bs.login()
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=40)).strftime('%Y-%m-%d')
        rs = bs.query_history_k_data_plus(
            'sh.000001',
            'date,close',
            start_date=start,
            end_date=end,
            frequency='d'
        )
        df = rs.get_data()
        bs.logout()
        df['close'] = df['close'].astype(float)
        prices = df['close'].values
        
        if len(prices) < 20:
            return 'neutral', 0.0
        
        returns = (prices[-1] - prices[-20]) / prices[-20]
        ma5 = np.mean(prices[-5:])
        ma20 = np.mean(prices[-20:])
        trend = (ma5 - ma20) / ma20
        
        if returns > 0.05 and trend > 0.02:
            return 'bull', returns
        elif returns < -0.05 and trend < -0.02:
            return 'bear', returns
        else:
            return 'neutral', returns
        
    except Exception as e:
        print(f"⚠️ 市场环境检测失败: {e}，默认震荡市")
        return 'neutral', 0.0


# ════════════════════════════════════════
# 第三模块：三模式评分引擎
# ════════════════════════════════════════

def score_bull_mode(prices, current):
    """
    牛市模式：趋势追踪
    选强势股，均线多头，动量强
    """
    prices = np.array(prices, dtype=float)
    score = 50.0
    notes = []

    ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else current
    ma10 = np.mean(prices[-10:]) if len(prices) >= 10 else current
    ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current

    # 均线多头排列（最重要）
    if ma5 > ma10 > ma20:
        score += 25
        notes.append("均线多头(+25)")
    elif ma5 > ma10:
        score += 10
        notes.append("短期多头(+10)")
    else:
        score -= 15
        notes.append("均线空头(-15)")

    # MACD 金叉
    macd = calc_macd_diff(prices)
    if macd > 0:
        score += 15
        notes.append("MACD金叉(+15)")
    else:
        score -= 10
        notes.append("MACD死叉(-10)")

    # 20日动量
    mom = calc_momentum(prices, 20)
    if mom > 0.10:
        score += 15
        notes.append(f"强动量{mom*100:.0f}%(+15)")
    elif mom > 0.05:
        score += 8
        notes.append(f"动量{mom*100:.0f}%(+8)")
    elif mom < -0.05:
        score -= 10
        notes.append(f"负动量{mom*100:.0f}%(-10)")

    # 价格在MA20上方（趋势确认）
    dev = (current - ma20) / ma20
    if 0.02 < dev < 0.15:
        score += 10
        notes.append(f"MA20上方{dev*100:.0f}%(+10)")
    elif dev > 0.15:
        score -= 5
        notes.append(f"偏离过大(-5)")

    return round(max(0, min(100, score)), 1), ' | '.join(notes)


def score_neutral_mode(prices, current):
    """
    震荡市模式：超卖反弹
    选低位超卖股，等待均值回归
    """
    prices = np.array(prices, dtype=float)
    score = 50.0
    notes = []

    rsi = calc_rsi(prices)
    if rsi <= 20:
        score += 30
        notes.append(f"RSI={rsi}极端超卖(+30)")
    elif rsi <= 30:
        score += 20
        notes.append(f"RSI={rsi}超卖(+20)")
    elif rsi <= 40:
        score += 10
        notes.append(f"RSI={rsi}偏弱(+10)")
    elif rsi >= 80:
        score -= 30
        notes.append(f"RSI={rsi}极端超买(-30)")
    elif rsi >= 70:
        score -= 20
        notes.append(f"RSI={rsi}超买(-20)")

    macd = calc_macd_diff(prices)
    score += 15 if macd > 0 else -15
    notes.append("MACD金叉(+15)" if macd > 0 else "MACD死叉(-15)")

    ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current
    dev = (current - ma20) / ma20
    if dev < -0.05:
        score += 10
        notes.append(f"低于MA20 {abs(dev)*100:.0f}%(+10)")
    elif dev > 0.05:
        score -= 10
        notes.append(f"高于MA20 {dev*100:.0f}%(-10)")

    return round(max(0, min(100, score)), 1), ' | '.join(notes)


def score_bear_mode(prices, current):
    """
    熊市模式：防御低波动
    选低波动、抗跌的防御性股票
    """
    prices = np.array(prices, dtype=float)
    score = 50.0
    notes = []

    # 低波动率（熊市中最重要）
    vol = calc_volatility(prices, 20)
    if vol < 0.20:
        score += 25
        notes.append(f"低波动{vol*100:.0f}%(+25)")
    elif vol < 0.30:
        score += 10
        notes.append(f"中波动{vol*100:.0f}%(+10)")
    else:
        score -= 15
        notes.append(f"高波动{vol*100:.0f}%(-15)")

    # 近60日最大回撤
    if len(prices) >= 60:
        peak = np.max(prices[-60:])
        drawdown = (current - peak) / peak
        if drawdown > -0.10:
            score += 20
            notes.append(f"回撤小{drawdown*100:.0f}%(+20)")
        elif drawdown > -0.20:
            score += 5
            notes.append(f"回撤中{drawdown*100:.0f}%(+5)")
        else:
            score -= 15
            notes.append(f"回撤大{drawdown*100:.0f}%(-15)")

    # 价格在年线附近（支撑位）
    if len(prices) >= 250:
        ma250 = np.mean(prices[-250:])
        dev = (current - ma250) / ma250
        if -0.05 < dev < 0.05:
            score += 10
            notes.append("年线支撑(+10)")

    return round(max(0, min(100, score)), 1), ' | '.join(notes)


# ════════════════════════════════════════
# 第四模块：主选股流程
# ════════════════════════════════════════

def run_selector():
    print("=" * 65)
    print("🔍 智能选股系统 v2.0")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # 第一步：检测市场环境
    print("\n【第一步】检测市场环境...")
    regime, market_ret = detect_market_regime()

    mode_name = {
        'bull': '🐂 牛市-趋势追踪模式',
        'neutral': '🐟 震荡市-超卖反弹模式',
        'bear': '🐻 熊市-防御模式'
    }[regime]
    print(f"\n✅ 当前模式: {mode_name}\n")

    # 第二步：获取全市场股票列表
    print("【第二步】获取全市场股票列表...")
    try:
        stocks = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,industry,list_date'
        )
        # 过滤
        stocks = stocks[~stocks['name'].str.contains('ST|退', na=False)]
        stocks = stocks[~stocks['ts_code'].str.startswith('688')]
        stocks = stocks[~stocks['ts_code'].str.startswith('8')]
        stocks = stocks[~stocks['ts_code'].str.startswith('4')]

        # 过滤上市不足6个月的新股
        cutoff = (datetime.today() - timedelta(days=180)).strftime('%Y%m%d')
        stocks = stocks[stocks['list_date'] <= cutoff]

        print(f"✅ 候选股票: {len(stocks)} 只")
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return []

    # 第三步：逐一计算因子评分
    print(f"\n【第三步】计算因子评分（预计15-25分钟）...")

    end = datetime.today().strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=180)).strftime('%Y%m%d')

    candidates = []
    total = len(stocks)
    errors = 0

    for i, row in stocks.iterrows():
        ts_code = row['ts_code']
        name = row['name']

        try:
            df = pro.daily(
                ts_code=ts_code,
                start_date=start,
                end_date=end,
                fields='trade_date,close,vol,amount'
            )

            if df is None or len(df) < MIN_TRADE_DAYS:
                continue

            df = df.sort_values('trade_date')
            prices = df['close'].astype(float).values
            current = prices[-1]

            # 价格过滤
            if current < 3.0 or current > 300.0:
                continue

            # 成交额过滤（万元）
            avg_amount = df['amount'].astype(float).tail(5).mean() / 10000
            if avg_amount < MIN_AMOUNT:
                continue

            # 按模式评分
            if regime == 'bull':
                score, reason = score_bull_mode(prices, current)
                threshold = 70  # 牛市要求更高分
            elif regime == 'bear':
                score, reason = score_bear_mode(prices, current)
                threshold = 65
            else:
                score, reason = score_neutral_mode(prices, current)
                threshold = 60

            # 只保留高分股票
            if score >= threshold:
                candidates.append({
                    'code': ts_code.split('.')[0],
                    'ts_code': ts_code,
                    'name': name,
                    'industry': row.get('industry', ''),
                    'price': round(current, 2),
                    'score': score,
                    'reason': reason,
                    'mode': regime,
                    'amount': round(avg_amount, 0)
                })

        except Exception:
            errors += 1
            continue

        # 进度显示
        if (i + 1) % 500 == 0:
            pct = (i + 1) / total * 100
            print(f" 进度: {i+1}/{total} "
                  f"({pct:.0f}%) | "
                  f"候选: {len(candidates)}只 | "
                  f"时间: {datetime.now().strftime('%H:%M:%S')}")

        time.sleep(0.12)  # Tushare 限速

    # 第四步：排序取前N，行业分散
    print(f"\n【第四步】筛选最优组合...")
    candidates.sort(key=lambda x: x['score'], reverse=True)

    # 行业分散：同一行业最多选2只
    selected = []
    industry_count = {}
    for c in candidates:
        ind = c.get('industry', '其他')
        if industry_count.get(ind, 0) < 2:
            selected.append(c)
            industry_count[ind] = industry_count.get(ind, 0) + 1
        if len(selected) >= TOP_N:
            break

    # 第五步：输出结果
    print(f"\n{'='*65}")
    print(f"🏆 选股结果 | 模式: {mode_name}")
    print(f" 共扫描 {total} 只 | "
          f"高分候选 {len(candidates)} 只 | "
          f"最终选出 {len(selected)} 只")
    print(f"{'='*65}")
    print(f"{'#':<3} {'代码':<8} {'名称':<10} {'行业':<10} "
          f"{'现价':<8} {'得分':<6} 选股原因")
    print("-" * 75)

    watch_codes = []
    for i, s in enumerate(selected, 1):
        print(f"{i:<3} {s['code']:<8} {s['name']:<10} "
              f"{s['industry']:<10} ¥{s['price']:<8} "
              f"{s['score']:<6} {s['reason'][:35]}")
        watch_codes.append(s['code'])

    # 第六步：保存结果
    output = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'market_regime': regime,
        'market_ret30': round(market_ret * 100, 2),
        'mode': mode_name,
        'watch_list': watch_codes,
        'details': selected
    }

    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到 {WATCH_FILE}")
    print(f"📋 明日监控: {watch_codes}")
    print(f"{'='*65}")

    return watch_codes


if __name__ == "__main__":
    run_selector()
