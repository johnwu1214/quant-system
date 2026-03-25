#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股量化交易系统 v4.2 - 三档置信度模型
核心改进：矛盾信号降仓位，不消灭信号
- RSI极端值(<15 或 >85)保护
- 矛盾信号 → 降低仓位比例，不改变信号方向
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import numpy as np
from datetime import datetime
import time as time_module
from data_source_manager import RobustDataSourceManager
from portfolio_state import (
    load_state, save_state,
    add_position, remove_position, print_portfolio
)

dm = RobustDataSourceManager()

def load_watch_list():
    """
    加载股票监控池
    优先用昨日选股结果，否则用默认列表
    """
    import os
    import json
    from datetime import datetime, timedelta
    
    # 必须保留的持仓股票
    state = load_state()
    held = list(state.get('positions', {}).keys())
    
    if os.path.exists('watch_list.json'):
        with open('watch_list.json', 'r') as f:
            data = json.load(f)
        
        # 容错：如果文件被写成列表格式，自动修复
        if isinstance(data, list):
            print("⚠️ watch_list.json 格式异常(列表)，自动修复为对象格式")
            wl = data if data else ['002737', '603960', '601006', '600329', '601116']
            fixed = {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "market_regime": "neutral",
                "mode": "🐟 震荡市-超卖反弹模式",
                "watch_list": wl,
                "details": []
            }
            with open('watch_list.json', 'w', encoding='utf-8') as fw:
                import json as _json
                _json.dump(fixed, fw, ensure_ascii=False, indent=2)
            print(f"✅ 已自动修复 watch_list.json，股票池: {wl}")
            data = fixed

        date = data.get('date', '未知')
        mode = data.get('mode', '未知模式')
        wl = data.get('watch_list', [])
        
        # 合并：持仓股票必须在监控列表里
        for code in held:
            if code not in wl:
                wl.insert(0, code)
        
        print(f"📋 股票池: {date} | {mode}")
        print(f" 监控列表: {wl}")
        if held:
            print(f" 持仓保留: {held}")
        return wl
    else:
        default = ['002737', '603960', '601006', 
                   '600329', '601116']
        # 同样合并持仓
        for code in held:
            if code not in default:
                default.insert(0, code)
        print(f"📋 使用默认股票池: {default}")
        return default

WATCH_LIST = load_watch_list()

# 评分阈值 - 调整更灵敏
BUY_THRESHOLD = 60  # 从65降到60
SELL_THRESHOLD = 40  # 从35提高到40

# RSI极端值保护
RSI_EXTREME_OVERSOLD = 20  # 从15提高到20，更容易触发
RSI_EXTREME_OVERBOUGHT = 80  # 从85降低到80

# 三档置信度对应仓位
POSITION_SIZES = {
    'HIGH': 0.15,   # 高置信：15%仓位
    'MEDIUM': 0.08, # 中置信：8%仓位  
    'LOW': 0.04,    # 低置信：4%仓位
}


def calc_rsi(prices, period=14):
    """计算RSI"""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-(period+1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_g = gains.mean()
    avg_l = losses.mean()
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def calc_ema(prices, period):
    """计算EMA"""
    if len(prices) < period:
        return float(prices[-1])
    k = 2 / (period + 1)
    ema = float(prices[-period])
    for p in prices[-period+1:]:
        ema = p * k + ema * (1 - k)
    return ema


def calc_macd_diff(prices):
    """计算MACD差值"""
    if len(prices) < 26:
        return 0.0
    return calc_ema(prices, 12) - calc_ema(prices, 26)


def compute_factor_signal(code, prices_list, current_price):
    """
    计算因子信号 - v4.2核心改进
    矛盾信号 → 降仓位，不消灭信号
    """
    prices = np.array(prices_list, dtype=float)
    current = current_price
    
    breakdown = {}
    score = 50.0
    has_conflict = False
    conflict_desc = ''
    
    # 1. RSI 评分（含极端值保护）- 扩大超卖超买范围
    rsi = calc_rsi(prices)
    rsi_extreme = False
    if rsi <= RSI_EXTREME_OVERSOLD:  # RSI=20也享受极端保护
        rsi_score = 30
        rsi_desc = f"RSI={rsi:.0f}极端超卖(+30)🛡️"
        rsi_extreme = True  # 极端值保护
    elif rsi < 35:  # 从30提高到35，更容易触发
        rsi_score = 25  # 从20提高到25
        rsi_desc = f"RSI={rsi:.0f}超卖(+25)"
    elif rsi > RSI_EXTREME_OVERBOUGHT:
        rsi_score = -30
        rsi_desc = f"RSI={rsi:.0f}极端超买(-30)🛡️"
        rsi_extreme = True
    elif rsi > 65:  # 从70降低到65
        rsi_score = -25  # 从-20提高到-25
        rsi_desc = f"RSI={rsi:.0f}超买(-25)"
    else:
        rsi_score = 0
        rsi_desc = f"RSI={rsi:.0f}中性"
    
    breakdown['rsi'] = {'score': rsi_score, 'desc': rsi_desc, 'value': rsi, 'extreme': rsi_extreme}
    score += rsi_score
    rsi_bullish = rsi_score > 0
    rsi_bearish = rsi_score < 0
    
    # 2. MACD 评分
    macd_diff = calc_macd_diff(prices)
    if macd_diff > 0:
        macd_score = 15
        macd_desc = "MACD金叉(+15)"
        macd_dir = 'UP'
    else:
        macd_score = -15
        macd_desc = "MACD死叉(-15)"
        macd_dir = 'DOWN'
    
    breakdown['macd'] = {'score': macd_score, 'desc': macd_desc}
    score += macd_score
    macd_bullish = macd_dir == 'UP'
    macd_bearish = macd_dir == 'DOWN'
    
    # 3. MA20 偏离
    ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current
    dev = (current - ma20) / ma20
    if dev < -0.05:
        ma_score = 10
        ma_desc = f"价格低于MA20 {abs(dev)*100:.1f}%(+10)"
    elif dev > 0.05:
        ma_score = -10
        ma_desc = f"价格高于MA20 {dev*100:.1f}%(-10)"
    else:
        ma_score = 0
        ma_desc = "价格在MA20附近"
    
    breakdown['ma20'] = {'score': ma_score, 'desc': ma_desc}
    score += ma_score
    
    # 4. 矛盾检测（只影响仓位，不影响得分！）
    if rsi_bullish and macd_bearish:
        if rsi_extreme:
            # RSI极端超卖：即使有死叉，维持中置信（极端保护）
            has_conflict = True
            conflict_desc = f"RSI={rsi:.0f}极端超卖🛡️+MACD死叉 → 极端值保护，维持8%仓位"
        else:
            # 普通超卖+死叉：降至低置信
            conflict_desc = "RSI超卖+MACD死叉矛盾 → 降至4%仓位"
    
    elif rsi_bearish and macd_bullish:
        if rsi_extreme:
            has_conflict = True
            conflict_desc = f"RSI={rsi:.0f}极端超买🛡️+MACD金叉 → 极端值保护，维持8%仓位"
        else:
            has_conflict = True
            conflict_desc = "RSI超买+MACD金叉矛盾 → 降至4%仓位"
    
    # 5. 归一化
    score = round(max(0, min(100, score)), 1)
    
    # 6. 信号方向
    if score >= BUY_THRESHOLD:
        signal = 'BUY'
    elif score <= SELL_THRESHOLD:
        signal = 'SELL'
    else:
        signal = 'HOLD'
    
    # 7. 三档置信度
    if not has_conflict:
        tier = 'HIGH'
    elif rsi_extreme:
        tier = 'MEDIUM'  # 极端值保护
    else:
        tier = 'LOW'
    
    # 8. 仓位比例
    if signal != 'HOLD':
        position_pct = POSITION_SIZES[tier]
    else:
        position_pct = 0.0
    
    # 9. 原因描述
    descs = [v['desc'] for v in breakdown.values() if v.get('score', 0) != 0]
    reason = ' | '.join(descs) if descs else '各因子中性'
    
    return {
        'symbol': code,
        'score': score,
        'signal': signal,
        'tier': tier,
        'position_pct': position_pct,
        'has_conflict': has_conflict,
        'conflict_desc': conflict_desc,
        'breakdown': breakdown,
        'reason': reason
    }


def run_cycle(state, cycle_num):
    print(f"\n{'='*60}")
    print(f"📊 第 {cycle_num} 轮交易 - v4.2三档置信度模型")
    print(f"{'='*60}")
    
    # 获取实时价格
    prices = dm.get_realtime_prices(WATCH_LIST)
    print(f"\n📈 实时行情:")
    for code, data in prices.items():
        print(f"   {code}: ¥{data['price']:.2f} ({data['change_pct']:+.2f}%) [{data['source']}]")
    
    # 因子分析
    print(f"\n📡 信号分析:")
    signals = {}
    for code in WATCH_LIST:
        if code not in prices:
            continue
        
        current = prices[code]['price']
        df = dm.get_history_kline(code, 30)
        if df.empty or len(df) < 20:
            continue
        
        prices_list = df['close'].values.tolist()
        sig = compute_factor_signal(code, prices_list, current)
        signals[code] = sig
        
        # 输出
        icon = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}[sig['signal']]
        tier_icon = {'HIGH': '💪', 'MEDIUM': '🤔', 'LOW': '⚠️'}[sig['tier']]
        
        print(f"   {icon} {code} 得分:{sig['score']}分 → {sig['signal']} {tier_icon}{sig['tier']}(仓位{sig['position_pct']*100:.0f}%)")
        print(f"    📊 {sig['reason']}")
        if sig['has_conflict']:
            print(f"    ⚡ {sig['conflict_desc']}")
    
    # ══════════════════════════════════════
    # 止损止盈检查（优先级高于信号判断）
    # ══════════════════════════════════════
    print(f"\n🛡️ 风控检查:")
    try:
        from risk_manager import RiskManager
        rm = RiskManager()
        positions = state['positions']
        for code, pos in list(positions.items()):
            if pos['shares'] <= 0:
                continue
            if code not in prices:
                continue
            current = prices[code]['price']
            cost = pos['cost']
            shares = pos['shares']
            risk = rm.monitor_position(code, current, cost, shares)
            pnl = risk['pnl_pct']
            for action in risk.get('actions', []):
                if action['action'] in ['止损', '止盈']:
                    remove_position(state, code, current)
                    emoji = '🔴' if action['action'] == '止损' else '🟢'
                    print(f"   {emoji} {action['action']} {code}: {pnl:.1%} → 强制卖出 @ ¥{current}")
                    print(f"      原因: {action['reason']}")
                    break
            else:
                if risk['level'] == 'warning':
                    print(f"   ⚠️  {code}: 浮亏 {pnl:.1%} 接近止损线，注意观察")
                else:
                    print(f"   ✅ {code}: 盈亏 {pnl:.1%} 正常")
    except Exception as e:
        print(f"   ⚠️ 风控检查失败: {e}")

    # 执行交易
    print(f"\n💰 交易执行:")
    
    for code, sig in signals.items():
        if code not in prices:
            continue
        
        current = prices[code]['price']
        positions = state['positions']
        has_pos = code in positions and positions[code]['shares'] > 0
        
        if sig['signal'] == 'BUY':
            if has_pos:
                cost = positions[code]['cost']
                profit_pct = (current - cost) / cost * 100
                print(f"   ⏭️ 跳过 {code}: 已持仓{positions[code]['shares']}股，盈利{profit_pct:.1f}%")
            else:
                add_position(state, code, 100, current)
                print(f"   ✅ 买入 {code}: 100股 @ ¥{current} "
                      f"(置信度{sig['tier']}, 仓位{sig['position_pct']*100:.0f}%)")
        
        elif sig['signal'] == 'SELL':
            if has_pos:
                remove_position(state, code, current)
                print(f"   ✅ 卖出 {code} @ ¥{current}")
            else:
                print(f"   ⏭️ 跳过 {code}: 无持仓")
        
        else:  # HOLD
            if has_pos:
                print(f"   ⏭️ {code}: 持有")
            else:
                print(f"   ⏭️ {code}: 因子评分{sig['score']}分，无明确信号")
    
    # 持仓状态
    print(f"\n📋 持仓状态:")
    total_value = state['cash']
    for code, pos in state['positions'].items():
        if code in prices:
            current = prices[code]['price']
            profit = (current - pos['cost']) / pos['cost'] * 100
            total_value += pos['shares'] * current
            emoji = "🟢" if profit >= 0 else "🔴"
            print(f"   {emoji} {code}: {pos['shares']}股 @ "
                  f"成本{pos['cost']:.2f}/现{current:.2f} ({profit:+.2f}%)")
    
    print(f"\n💵 现金: ¥{state['cash']:.2f} | 总资产: ¥{total_value:.2f}")


def main():
    print("="*60)
    print("🚀 A股量化交易系统 v4.2 - 三档置信度模型")
    print("="*60)
    print(f"监控: {WATCH_LIST}")
    print(f"阈值: 买入>={BUY_THRESHOLD}, 卖出<={SELL_THRESHOLD}")
    print(f"极端值保护: RSI<{RSI_EXTREME_OVERSOLD} 或 >{RSI_EXTREME_OVERBOUGHT}")
    
    state = load_state()
    
    i = 1
    while True:
        now = datetime.now()
        t = now.hour * 60 + now.minute
        
        # 9:30 之前不交易（避免集合竞价数据异常）
        if t < 570:
            print(f"\r⏸️ 等待开盘 {now.strftime('%H:%M:%S')}", 
                  end='', flush=True)
            time_module.sleep(30)
            continue
        
        # 14:50 收盘前触发自动选股
        if t == 890:
            print("\n🔍 收盘前触发自动选股，明日股票池更新中...")
            import subprocess
            subprocess.Popen(['python3', 'stock_selector.py'])
        
        # 15:00 收盘停止
        if t >= 900:
            print(f"\n⏰ 已到15:00，收盘停止")
            break
        
        run_cycle(state, i)
        print("\n⏳ 等待下一轮...")
        time_module.sleep(60)
        i += 1
    
    print("\n" + "="*60)
    print("✅ 交易结束")
    print("="*60)


if __name__ == "__main__":
    main()
