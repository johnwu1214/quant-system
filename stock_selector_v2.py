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
    检测当前市场环境 - 使用 BaoStock sh.000300 指数，零 Qlib 依赖
    返回：'bull'（牛市）/ 'neutral'（震荡）/ 'bear'（熊市）
    判断逻辑：
      牛市  = 20日收益>5% 且 MA5>MA20
      熊市  = 20日收益<-5% 且 MA5<MA20
      震荡市 = 其他
    """
    import numpy as np
    import baostock as bs
    from datetime import datetime, timedelta

    try:
        # 取过去 90 天数据，确保至少有 60 个交易日
        end_date   = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')

        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            'sh.000300',
            'date,close',
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag='3'
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()

        if not rows:
            # BaoStock 也失败，尝试 mootdx 实时兜底
            try:
                import sys, os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from data_source import get_realtime_price_mootdx
                r = get_realtime_price_mootdx('000300')
                if r and r.get('price'):
                    print('  ⚠️ BaoStock 指数无数据，使用实时价格估算，默认震荡市')
                    return 'neutral', 0.0
            except Exception:
                pass
            print('  ⚠️ 指数数据获取失败，默认震荡市')
            return 'neutral', 0.0

        # 提取收盘价序列（过滤空值）
        prices = []
        for row in rows:
            try:
                v = float(row[1])
                if v > 0:
                    prices.append(v)
            except (ValueError, IndexError):
                continue

        if len(prices) < 25:
            print(f'  ⚠️ 指数数据不足({len(prices)}条)，默认震荡市')
            return 'neutral', 0.0

        prices = np.array(prices)
        ret20  = (prices[-1] - prices[-20]) / prices[-20]      # 20日收益率
        ma5    = np.mean(prices[-5:])
        ma20   = np.mean(prices[-20:])
        ma60   = np.mean(prices[-60:]) if len(prices) >= 60 else ma20
        trend  = (ma5 - ma20) / ma20                           # MA5/MA20 趋势
        vol20  = np.std(np.diff(prices[-21:])) / np.mean(prices[-21:])  # 波动率

        print(f'  20日收益: {ret20*100:+.2f}%  MA5/MA20趋势: {trend*100:+.2f}%  波动率: {vol20*100:.2f}%')

        if ret20 > 0.05 and trend > 0.01:
            regime = 'bull'
        elif ret20 < -0.05 and trend < -0.01:
            regime = 'bear'
        else:
            regime = 'neutral'

        print(f'  市场判断: {regime}  (sh.000300 {len(prices)}条数据)')
        return regime, ret20

    except Exception as e:
        print(f'  ⚠️ 市场状态检测异常: {e}，默认震荡市')
        return 'neutral', 0.0
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


    # 第二步：获取沪深300成分股（BaoStock，完全免费）
    print("【第二步】获取沪深300成分股...")
    try:
        import baostock as bs
        import pandas as pd
        bs.login()
        rs = bs.query_hs300_stocks()
        rows = []
        while rs.error_code == '0' and rs.next():
            r = rs.get_row_data()
            code6 = r[1].split('.')[1] if '.' in r[1] else r[1]
            if code6.startswith('688') or code6.startswith('8') or code6.startswith('4'):
                continue
            rows.append({'ts_code': code6, 'name': r[2]})
        bs.logout()
        if not rows:
            raise Exception("BaoStock 返回为空")
        stocks = pd.DataFrame(rows)
        print(f"✅ 候选股票(沪深300): {len(stocks)} 只")
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

    # BaoStock 循环外一次登录，避免反复握手卡死
    import baostock as bs
    bs.login()
    end_bs   = datetime.today().strftime('%Y-%m-%d')
    start_bs = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

    for i, row in stocks.iterrows():
        ts_code = row['ts_code']   # 6位代码，如 300502
        name    = row['name']
        bs_code = ('sh.' if ts_code.startswith('6') else 'sz.') + ts_code

        try:
            rs2 = bs.query_history_k_data_plus(
                bs_code,
                'date,close,volume,amount',
                start_date=start_bs, end_date=end_bs,
                frequency='d', adjustflag='3'
            )
            bs_rows = []
            while rs2.error_code == '0' and rs2.next():
                bs_rows.append(rs2.get_row_data())

            if not bs_rows:
                if errors <= 3: print(f"  ⚠️ 无数据: {bs_code} err={rs2.error_code} msg={rs2.error_msg}")
                errors += 1
                continue

            df = pd.DataFrame(bs_rows, columns=['date','close','vol','amount'])
            df = df[df['close'] != ''].copy()
            for col in ['close','vol','amount']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna(subset=['close'])
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
                # P2: 从成分股查询结果提取股票名称
                name_val = row.get('stock_name', row.get('code_name', bs_code.split('.')[-1]))
                candidates.append({
                    'symbol': ts_code.split('.')[0],
                    'code':   ts_code.split('.')[0],
                    'ts_code': ts_code,
                    'name': name,
                    'industry': '其他',
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
        if (i + 1) % 50 == 0:
            pct = (i + 1) / total * 100
            print(f" 进度: {i+1}/{total} "
                  f"({pct:.0f}%) | "
                  f"候选: {len(candidates)}只 | "
                  f"时间: {datetime.now().strftime('%H:%M:%S')}")

        time.sleep(0.02)  # BaoStock 无限速，适当间隔

    bs.logout()  # 循环结束，释放连接

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

    # 合并持仓股（持仓股必须在监控列表）
    try:
        with open('portfolio_state.json') as f:
            port = json.load(f)
        held = list(port.get('positions', {}).keys())
        for code in held:
            if code not in watch_codes:
                watch_codes.insert(0, code)
        print(f'📌 持仓股已合并: {held}')
    except Exception as e:
        print(f'⚠️ 持仓合并失败: {e}')

    # 第六步：买入前深度审查
    print("\n【第六步】买入前深度审查...")
    try:
        from pre_buy_checker import check_candidates
        _thresh = 70 if regime == 'bull' else (55 if regime == 'bear' else 60)
        print(f'  审查阈值: {_thresh}分（{regime}市）')
        check_results = check_candidates(selected, verbose=True, threshold=_thresh)
        cr_map = {r['symbol']: r for r in check_results}
        for s in selected:
            sym = s.get('symbol', s.get('code', ''))
            if sym in cr_map:
                r = cr_map[sym]
                s['check_score']   = r['score']
                s['check_verdict'] = r['verdict']
                s['check_passed']  = r['passed']
                s['check_reason']  = r['reason']
        # 推荐买入列表（通过审查的）
        passed_codes = [r['symbol'] for r in check_results if r['passed']]
        print(f"\n  ✅ 通过审查: {passed_codes}")
    except Exception as e:
        print(f"  ⚠️ 审查模块异常({e})，跳过")
        passed_codes = watch_codes  # 降级：不过滤

    # 第七步：保存结果
    # ── final_watch = 通过审查的股票 + 持仓股（始终保留）──
    final_watch = list(dict.fromkeys(passed_codes)) if passed_codes else []

    # 持仓股始终保留在监控列表首位
    held = []
    try:
        with open('portfolio_state.json') as f:
            port = json.load(f)
        held = list(port.get('positions', {}).keys())
        for code in held:
            if code not in final_watch:
                final_watch.insert(0, code)
    except Exception:
        pass

    # P1 修复：最终去重，保持顺序
    final_watch = list(dict.fromkeys(final_watch))

    if not final_watch:
        print('⚠️ 审查后无股票通过，仅保留持仓监控')

    output = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'market_regime': regime,
        'market_ret30': round(market_ret * 100, 2),
        'mode': mode_name,
        'watch_list': final_watch,
        'passed_list': [c for c in final_watch if c not in held],
        'details': selected
    }

    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到 {WATCH_FILE}")
    print(f"📋 明日监控: {final_watch}")
    print(f"  其中持仓股: {held}")
    print(f"  新通过审查: {[c for c in final_watch if c not in held]}")
    print(f"{'='*65}")

    return final_watch


if __name__ == "__main__":
    run_selector()
