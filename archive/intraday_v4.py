#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股盘中交易系统 v4.1 - 信号层与执行层分离版
✓ 真实实时行情 (腾讯直连)
✓ 因子驱动信号 (MA + RSI + MACD)
✓ 矛盾信号折扣机制
✓ 信号层与执行层分离
✓ 三层风控
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import json
import os
from datetime import datetime, time
import time as time_module
import numpy as np
from data_source_manager import RobustDataSourceManager

# 初始化数据管理器
dm = RobustDataSourceManager()

# 监听的股票列表
WATCH_LIST = ['603960', '600938', '600329', '002737']

# 评分阈值
BUY_THRESHOLD = 65
SELL_THRESHOLD = 35
CONFLICT_DISCOUNT = 0.5


class FactorSignal:
    """纯因子分析结果 - 与持仓状态完全无关"""
    def __init__(self, symbol, raw_score, signal, reason, breakdown, conflicts):
        self.symbol = symbol
        self.raw_score = raw_score  # 0-100
        self.signal = signal  # BUY/SELL/HOLD
        self.reason = reason
        self.breakdown = breakdown
        self.conflicts = conflicts


class ExecutionDecision:
    """执行决策"""
    def __init__(self, symbol, action, factor_signal, skip_reason=""):
        self.symbol = symbol
        self.action = action  # BUY/SELL/ADD/HOLD
        self.factor_signal = factor_signal
        self.skip_reason = skip_reason


def calculate_rsi(prices, period=14):
    """计算RSI"""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calculate_ema(prices, period):
    """计算EMA"""
    if len(prices) < period:
        return float(prices[-1])
    k = 2 / (period + 1)
    ema = float(prices[-period])
    for p in prices[-period+1:]:
        ema = p * k + ema * (1 - k)
    return ema


def compute_factor_signal(code, prices, current_price):
    """
    第一层：纯因子计算
    返回 FactorSignal（与持仓完全无关）
    """
    prices = np.array(prices, dtype=float)
    current = current_price
    
    breakdown = {}
    conflicts = []
    score = 50.0
    
    # 1. RSI(14)
    rsi = calculate_rsi(prices, 14)
    if rsi < 20:
        rsi_bonus = 30
        rsi_desc = f"RSI={rsi:.0f}极度超卖(+{rsi_bonus})"
    elif rsi < 30:
        rsi_bonus = 20
        rsi_desc = f"RSI={rsi:.0f}超卖(+{rsi_bonus})"
    elif rsi > 80:
        rsi_bonus = -30
        rsi_desc = f"RSI={rsi:.0f}极度超买({rsi_bonus})"
    elif rsi > 70:
        rsi_bonus = -20
        rsi_desc = f"RSI={rsi:.0f}超买({rsi_bonus})"
    else:
        rsi_bonus = 0
        rsi_desc = f"RSI={rsi:.0f}中性"
    
    breakdown['rsi'] = {'score': rsi_bonus, 'desc': rsi_desc, 'value': rsi}
    rsi_direction = 'UP' if rsi_bonus > 0 else ('DOWN' if rsi_bonus < 0 else 'NEUTRAL')
    
    # 2. MACD
    ema_fast = calculate_ema(prices, 12)
    ema_slow = calculate_ema(prices, 26)
    macd_diff = ema_fast - ema_slow
    
    if macd_diff > 0:
        macd_bonus = 15
        macd_desc = f"MACD金叉(+{macd_bonus})"
        macd_direction = 'UP'
    else:
        macd_bonus = -15
        macd_desc = f"MACD死叉({macd_bonus})"
        macd_direction = 'DOWN'
    
    breakdown['macd'] = {'score': macd_bonus, 'desc': macd_desc, 'direction': macd_direction}
    
    # 3. MA20 偏离
    ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current
    deviation = (current - ma20) / ma20
    if deviation < -0.05:
        ma_bonus = 10
        ma_desc = f"价格低于MA20 {abs(deviation)*100:.1f}%(+{ma_bonus})"
    elif deviation > 0.05:
        ma_bonus = -10
        ma_desc = f"价格高于MA20 {deviation*100:.1f}%({ma_bonus})"
    else:
        ma_bonus = 0
        ma_desc = "价格在MA20附近"
    breakdown['ma20'] = {'score': ma_bonus, 'desc': ma_desc}
    
    # 4. 矛盾信号检测与折扣
    # RSI超卖 但 MACD死叉 → 可能继续下跌，RSI信号打折
    if rsi_bonus > 0 and macd_direction == 'DOWN':
        original_rsi = rsi_bonus
        rsi_bonus = int(rsi_bonus * CONFLICT_DISCOUNT)
        breakdown['rsi']['score'] = rsi_bonus
        breakdown['rsi']['desc'] += f" [死叉折扣×{CONFLICT_DISCOUNT}→+{rsi_bonus}]"
        conflicts.append(f"⚠️ RSI超卖+MACD死叉矛盾，RSI权重折半")
    
    # RSI超买 但 MACD金叉 → 追高风险，MACD信号打折
    if rsi_bonus < 0 and macd_direction == 'UP':
        original_macd = macd_bonus
        macd_bonus = int(macd_bonus * CONFLICT_DISCOUNT)
        breakdown['macd']['score'] = macd_bonus
        breakdown['macd']['desc'] += f" [超买折扣×{CONFLICT_DISCOUNT}→{macd_bonus}]"
        conflicts.append(f"⚠️ RSI超买+MACD金叉矛盾，MACD权重折半")
    
    # 5. 汇总评分
    total_score = 50 + rsi_bonus + macd_bonus + ma_bonus
    total_score = max(0, min(100, total_score))
    
    # 6. 确定信号方向
    if total_score >= BUY_THRESHOLD:
        signal = 'BUY'
    elif total_score <= SELL_THRESHOLD:
        signal = 'SELL'
    else:
        signal = 'HOLD'
    
    # 7. 组装原因
    factor_descs = [v['desc'] for v in breakdown.values() if v.get('score', 0) != 0]
    reason_parts = factor_descs + conflicts
    reason = ' | '.join(reason_parts) if reason_parts else '各因子中性'
    
    return FactorSignal(
        symbol=code,
        raw_score=round(total_score, 1),
        signal=signal,
        reason=reason,
        breakdown=breakdown,
        conflicts=conflicts
    )


def make_execution_decision(factor_signal, positions, cash, current_price):
    """
    第二层：执行决策
    综合因子信号 + 当前持仓 → 最终动作
    """
    code = factor_signal.symbol
    has_pos = code in positions and positions[code]['shares'] > 0
    
    # 决策矩阵
    if factor_signal.signal == 'BUY':
        if not has_pos:
            if cash >= current_price * 100:
                action = 'BUY'
                skip_reason = ""
            else:
                action = 'HOLD'
                skip_reason = f'资金不足(需¥{current_price*100:.0f}，现金¥{cash:.0f})'
        else:
            # 已持仓 → 判断是否符合加仓条件
            cost = positions[code]['avg_cost']
            profit_pct = (current_price - cost) / cost * 100
            if profit_pct > 5 and factor_signal.raw_score >= 75:
                action = 'ADD'
                skip_reason = ""
            else:
                action = 'HOLD'
                skip_reason = f'已持仓({positions[code]["shares"]}股)，盈利{profit_pct:.1f}%，不重复买入'
    
    elif factor_signal.signal == 'SELL':
        if has_pos:
            action = 'SELL'
            skip_reason = ""
        else:
            action = 'HOLD'
            skip_reason = '无持仓，跳过卖出信号'
    
    else:  # HOLD
        action = 'HOLD'
        skip_reason = f'因子评分{factor_signal.raw_score}分，无明确信号'
    
    return ExecutionDecision(code, action, factor_signal, skip_reason)


class Portfolio:
    """组合管理"""
    def __init__(self, cash=100000):
        self.cash = cash
        self.positions = {}  # {code: {'shares': 100, 'avg_cost': 25.0}}
    
    def buy(self, code, price, shares):
        cost = price * shares
        if cost > self.cash:
            return False, "资金不足"
        
        if code in self.positions:
            old_shares = self.positions[code]['shares']
            old_cost = self.positions[code]['avg_cost'] * old_shares
            new_shares = old_shares + shares
            new_cost = old_cost + cost
            self.positions[code] = {
                'shares': new_shares,
                'avg_cost': new_cost / new_shares
            }
        else:
            self.positions[code] = {
                'shares': shares,
                'avg_cost': price
            }
        
        self.cash -= cost
        return True, f"买入{code} {shares}股 @ ¥{price}"
    
    def sell(self, code, price, shares=None):
        if code not in self.positions:
            return False, "无持仓"
        
        pos = self.positions[code]
        if shares is None:
            shares = pos['shares']
        
        if shares > pos['shares']:
            shares = pos['shares']
        
        revenue = price * shares
        self.cash += revenue
        
        pos['shares'] -= shares
        if pos['shares'] <= 0:
            del self.positions[code]
        
        return True, f"卖出{code} {shares}股 @ ¥{price}"
    
    @property
    def total_value(self):
        return self.cash


def get_realtime_prices():
    """获取实时价格"""
    return dm.get_realtime_prices(WATCH_LIST)


def run_trading_cycle(portfolio, cycle_num):
    """执行一轮交易"""
    print(f"\n{'='*60}")
    print(f"📊 第 {cycle_num} 轮交易")
    print(f"{'='*60}")
    
    # 1. 获取实时价格
    prices = get_realtime_prices()
    print(f"\n📈 实时行情:")
    for code, data in prices.items():
        print(f"   {code}: ¥{data['price']:.2f} ({data['change_pct']:+.2f}%) [{data['source']}]")
    
    # 2. 因子分析（信号层 - 独立于持仓）
    print(f"\n📡 信号分析（因子层 - 独立于持仓）:")
    factor_signals = {}
    for code in WATCH_LIST:
        if code not in prices:
            continue
        
        current_price = prices[code]['price']
        
        # 获取历史数据
        df = dm.get_history_kline(code, 30)
        if df.empty or len(df) < 20:
            continue
        
        # 计算因子信号
        prices_list = df['close'].values.tolist()
        factor_signal = compute_factor_signal(code, prices_list, current_price)
        factor_signals[code] = factor_signal
        
        # 输出格式
        icon = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}[factor_signal.signal]
        print(f"   {icon} [{code}] 因子得分:{factor_signal.raw_score}分 → {factor_signal.signal}")
        print(f"    📊 {factor_signal.reason}")
        
        # 矛盾信号警告
        for conflict in factor_signal.conflicts:
            print(f"    {conflict}")
    
    # 3. 执行决策（综合持仓状态）
    print(f"\n💰 交易执行:")
    trades = 0
    for code, factor_signal in factor_signals.items():
        if code not in prices:
            continue
        
        current_price = prices[code]['price']
        
        # 执行决策
        decision = make_execution_decision(
            factor_signal, 
            portfolio.positions, 
            portfolio.cash,
            current_price
        )
        
        # 执行或跳过
        if decision.action == 'BUY':
            ok, msg = portfolio.buy(code, current_price, 100)
            if ok:
                print(f"   ✅ 买入 {code}: 100股 @ ¥{current_price}")
                trades += 1
            else:
                print(f"   ❌ 买入失败: {msg}")
        
        elif decision.action == 'SELL':
            ok, msg = portfolio.sell(code, current_price)
            if ok:
                print(f"   ✅ 卖出 {code} @ ¥{current_price}")
                trades += 1
            else:
                print(f"   ❌ 卖出失败: {msg}")
        
        elif decision.action == 'ADD':
            ok, msg = portfolio.buy(code, current_price, 100)
            if ok:
                print(f"   ➕ 加仓 {code}: 100股 @ ¥{current_price}")
                trades += 1
        
        else:
            # HOLD
            icon = '⏭️'
            if '已持仓' in decision.skip_reason:
                print(f"   {icon} 跳过 {code}: {decision.skip_reason}")
            elif '资金不足' in decision.skip_reason:
                print(f"   {icon} 跳过 {code}: {decision.skip_reason}")
            else:
                print(f"   {icon} {code}: {decision.skip_reason}")
    
    # 4. 持仓状态
    print(f"\n📋 持仓状态:")
    total_value = portfolio.cash
    for code, pos in portfolio.positions.items():
        if code in prices:
            current_price = prices[code]['price']
            value = pos['shares'] * current_price
            profit = (current_price - pos['avg_cost']) / pos['avg_cost'] * 100
            total_value += value
            emoji = "🟢" if profit >= 0 else "🔴"
            print(f"   {emoji} {code}: {pos['shares']}股 @ 成本{pos['avg_cost']:.2f}/现{current_price:.2f} ({profit:+.2f}%)")
    
    print(f"\n💵 现金: ¥{portfolio.cash:.2f} | 总资产: ¥{total_value:.2f}")
    
    return trades


def main():
    """主函数"""
    print("="*60)
    print("🚀 A股量化交易系统 v4.1 - 信号执行分离版")
    print("="*60)
    print(f"监控股票: {WATCH_LIST}")
    print(f"启动时间: {datetime.now()}")
    print(f"评分阈值: 买入>={BUY_THRESHOLD}分, 卖出<={SELL_THRESHOLD}分")
    print(f"矛盾折扣: RSI与MACD矛盾时×{CONFLICT_DISCOUNT}")
    
    # 初始化组合
    portfolio = Portfolio(cash=100000)
    
    # 运行交易轮次
    cycles = 3
    for i in range(1, cycles + 1):
        run_trading_cycle(portfolio, i)
        if i < cycles:
            print("\n⏳ 等待下一轮...")
            time_module.sleep(3)
    
    print("\n" + "="*60)
    print("✅ 交易结束")
    print("="*60)


if __name__ == "__main__":
    main()
