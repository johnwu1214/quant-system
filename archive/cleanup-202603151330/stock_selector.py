#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动选股脚本 - 每日收盘后运行
从A股全市场筛选明日监控股票池
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

# ── 选股参数配置 ──
TOP_N = 10  # 最终选出股票数量
MIN_DAYS = 60  # 历史数据最少天数
MIN_PRICE = 5.0  # 最低股价（排除垃圾股）
MAX_PRICE = 500.0  # 最高股价（避免买不起）
MIN_RSI = 20  # RSI下限（超卖区间）
MAX_RSI = 40  # RSI上限（不追高）
MA20_DEV_MIN = -0.15  # 价格低于MA20最多15%
MA20_DEV_MAX = -0.03  # 价格低于MA20至少3%
WATCH_LIST_FILE = "watch_list.json"  # 输出文件


def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-(period+1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g = gains.mean()
    avg_l = losses.mean()
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 1)


def calc_ema(prices, period):
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


def calc_score(prices, current_price):
    """计算选股综合得分（与交易系统使用相同逻辑）"""
    prices = np.array(prices, dtype=float)
    score = 50.0

    # RSI
    rsi = calc_rsi(prices)
    if rsi <= 20:
        score += 30
    elif rsi <= 30:
        score += 20
    elif rsi <= 40:
        score += 10
    elif rsi >= 70:
        score -= 20
    elif rsi >= 80:
        score -= 30

    # MACD
    macd_diff = calc_macd_diff(prices)
    score += 15 if macd_diff > 0 else -15

    # MA20 偏离
    ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current_price
    dev = (current_price - ma20) / ma20
    if dev < -0.05:
        score += 10
    elif dev > 0.05:
        score -= 10

    # 均线多头/空头排列
    ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else current_price
    ma10 = np.mean(prices[-10:]) if len(prices) >= 10 else current_price
    if ma5 > ma10 > ma20:
        score += 5  # 多头排列加分
    elif ma5 < ma10 < ma20:
        score -= 5  # 空头排列减分

    return round(max(0, min(100, score)), 1), rsi, dev, macd_diff


def get_all_stocks():
    """获取A股全市场股票列表"""
    print("📡 登录baostock...")
    lg = bs.login()
    if lg.error_code != '0':
        print(f"❌ 登录失败: {lg.error_msg}")
        return []

    print("📥 获取A股股票列表...")
    rs = bs.query_stock_basic()
    stocks = []
    while rs.error_code == '0' and rs.next():
        stock = rs.get_row_data()
        code = stock[0]
        name = stock[1]
        # stock[4] = type, 1=普通股票, 4=可转债, 5=ETF, 2=指数
        # 过滤: 沪市600/601/603/688开头，深市000/001/002/003/300开头，type=1(股票)
        if stock[4] == '1':  # 只保留普通股票
            if (code.startswith('sh.60') or code.startswith('sh.68') or 
                code.startswith('sz.00') or code.startswith('sz.30')):
                stocks.append({'code': code, 'name': name})

    bs.logout()
    print(f"✅ 获取到 {len(stocks)} 只A股股票")
    return stocks


def get_history_kline(code, days=60):
    """获取历史K线数据"""
    bs.login()
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume",
        start_date=(datetime.now() - timedelta(days=days+30)).strftime('%Y-%m-%d'),
        end_date=datetime.now().strftime('%Y-%m-%d'),
        frequency="d",
        adjustflag="3"
    )
    data = []
    while rs.error_code == '0' and rs.next():
        data.append(rs.get_row_data())
    bs.logout()

    if not data:
        return None

    df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    df = df[df['close'] != '']
    if len(df) < MIN_DAYS:
        return None

    df['close'] = df['close'].astype(float)
    return df


def analyze_stock(code, name):
    """分析单只股票"""
    df = get_history_kline(code)
    if df is None:
        return None

    try:
        current_price = df['close'].iloc[-1]
        if current_price < MIN_PRICE or current_price > MAX_PRICE:
            return None

        prices = df['close'].values
        score, rsi, dev, macd = calc_score(prices, current_price)

        # RSI过滤
        if rsi < MIN_RSI or rsi > MAX_RSI:
            return None

        # MA20偏离过滤
        if dev > MA20_DEV_MIN or dev < MA20_DEV_MAX:
            return None

        return {
            'code': code.replace('sh.', '').replace('sz.', ''),
            'name': name,
            'price': current_price,
            'score': score,
            'rsi': rsi,
            'dev': dev,
            'macd': macd
        }
    except Exception as e:
        return None


def main():
    print("="*60)
    print("🔍 自动选股系统 - 每日股票池更新")
    print("="*60)
    print(f"参数: TOP_N={TOP_N}, MIN_DAYS={MIN_DAYS}, RSI范围={MIN_RSI}-{MAX_RSI}")
    print(f"MA20偏离范围: {MA20_DEV_MIN*100:.0f}% ~ {MA20_DEV_MAX*100:.0f}%")

    start_time = time.time()

    # 获取全市场股票
    stocks = get_all_stocks()
    if not stocks:
        print("❌ 无法获取股票列表")
        return

    # 筛选分析
    candidates = []
    total = len(stocks)
    print(f"\n📊 开始分析 {total} 只股票...")

    for i, stock in enumerate(stocks):
        if (i+1) % 100 == 0:
            print(f"  进度: {i+1}/{total} ({100*(i+1)//total}%)")

        result = analyze_stock(stock['code'], stock['name'])
        if result:
            candidates.append(result)

    if not candidates:
        print("❌ 没有符合条件的股票")
        # 备用: 返回默认股票池
        candidates = [
            {'code': '603960', 'name': '克来机电', 'score': 65},
            {'code': '600938', 'name': '中国海油', 'score': 60},
            {'code': '600329', 'name': '达仁堂', 'score': 55},
            {'code': '002737', 'name': '葵花药业', 'score': 50},
        ]
        print("📋 使用默认股票池")

    # 按得分排序
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_stocks = candidates[:TOP_N]

    # 输出结果
    print(f"\n✅ 选出 {len(top_stocks)} 只候选股票:")
    for i, s in enumerate(top_stocks, 1):
        rsi_str = f"RSI={s.get('rsi', 'N/A')}"
        dev_str = f"MA20偏离={s.get('dev', 0)*100:.1f}%" if 'dev' in s else ""
        print(f"  {i}. {s['code']} {s['name']}: 得分{s['score']} | {rsi_str} {dev_str}")

    # 保存到文件
    watch_list = [s['code'] for s in top_stocks]
    with open(WATCH_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watch_list, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"\n💾 已保存到 {WATCH_LIST_FILE}")
    print(f"⏱️ 选股耗时: {elapsed:.1f}秒")
    print("="*60)


if __name__ == "__main__":
    main()
