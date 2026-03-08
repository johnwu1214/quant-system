#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股盘中交易系统 v3.0 - 修复版
✓ 真实实时行情 (腾讯直连)
✓ 因子驱动信号 (MA + RSI + MACD)
✓ 三层风控
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import json
import os
from datetime import datetime, time
import time as time_module
from data_source_manager import RobustDataSourceManager

# 初始化数据管理器
dm = RobustDataSourceManager()

# 监听的股票列表
WATCH_LIST = ['603960', '600938', '600329', '002737']


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


def generate_factor_signals(prices, portfolio):
    """
    基于真实因子的信号生成
    """
    signals = {}
    
    for code in WATCH_LIST:
        if code not in prices:
            continue
        
        current_price = prices[code]['price']
        
        # 获取历史数据计算因子
        df = dm.get_history_kline(code, 30)
        if df.empty or len(df) < 20:
            signals[code] = {
                'decision': '持有',
                'confidence': 50,
                'reason': '数据不足'
            }
            continue
        
        # 计算因子
        df = dm.calculate_ma(df, [5, 10, 20])
        df = dm.calculate_rsi(df, 6)
        df = dm.calculate_macd(df)
        
        # 最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        ma5 = latest['ma5']
        ma10 = latest['ma10']
        ma20 = latest['ma20']
        rsi = latest['rsi6']
        macd = latest['macd']
        signal = latest['signal']
        
        # ─────────────────────────────────────
        # 因子评分（输出真实分数）
        # ─────────────────────────────────────
        score = 50  # 基础分
        reasons = []
        
        # RSI 评分（权重最高）
        if rsi < 20:
            score += 30
            reasons.append(f"RSI={rsi:.0f}极度超卖(+30)")
        elif rsi < 30:
            score += 25
            reasons.append(f"RSI={rsi:.0f}超卖(+25)")
        elif rsi > 80:
            score -= 30
            reasons.append(f"RSI={rsi:.0f}极度超买(-30)")
        elif rsi > 70:
            score -= 25
            reasons.append(f"RSI={rsi:.0f}超买(-25)")
        
        # MA 交叉评分
        if prev['ma5'] <= prev['ma20'] and latest['ma5'] > latest['ma20']:
            score += 20
            reasons.append("MA金叉(+20)")
        elif prev['ma5'] >= prev['ma20'] and latest['ma5'] < latest['ma20']:
            score -= 20
            reasons.append("MA死叉(-20)")
        
        # MACD 评分
        if macd > signal:
            score += 15
            reasons.append("MACD金叉(+15)")
        elif macd < signal:
            score -= 15
            reasons.append("MACD死叉(-15)")
        
        # 价格偏离均线
        if current_price < ma20 * 0.95:
            score += 10
            reasons.append("价格远低于MA20(+10)")
        elif current_price > ma20 * 1.05:
            score -= 10
            reasons.append("价格远高于MA20(-10)")
        
        # 持仓检查
        has_position = code in portfolio.positions
        
        # 归一化到 0-100
        score = max(0, min(100, score))
        
        # 决策阈值（65分以上触发）
        if has_position:
            # 持仓股：分数低于40才卖出
            if score <= 40:
                decision = '卖出'
                confidence = 50 + (50 - score)
            else:
                decision = '持有'
                confidence = score
        else:
            # 无持仓：分数高于60才买入
            if score >= 60:
                decision = '买入'
                confidence = score
            else:
                decision = '持有'
                confidence = score
        
        signals[code] = {
            'decision': decision,
            'confidence': confidence,
            'reason': ' | '.join(reasons) if reasons else '无明确信号',
            'factors': {
                'ma5': round(ma5, 2),
                'ma20': round(ma20, 2),
                'rsi': round(rsi, 1),
                'macd': round(macd, 2),
                'price': current_price,
                'score': score  # 原始评分
            }
        }
    
    return signals


def check_risk_control(portfolio, action, code, price, signals):
    """风控检查"""
    # 1. 持仓上限
    if action == '买入':
        if len(portfolio.positions) >= 4:
            return False, "持仓上限4只"
    
    # 2. 单股仓位上限 20%
    if action == '买入':
        if code in portfolio.positions:
            pos = portfolio.positions[code]
            pos_value = pos['shares'] * price
            total = portfolio.total_value + pos_value
            if pos_value / total > 0.20:
                return False, f"单股仓位超20%"
    
    # 3. 现金不足
    if action == '买入':
        needed = price * 100  # 最小100股
        if portfolio.cash < needed:
            return False, "现金不足"
    
    # 4. 同一股票交易冷静期（简单实现）
    # 可以记录最近交易时间
    
    return True, "通过"


def run_trading_cycle(portfolio, cycle_num):
    """执行一轮交易"""
    print(f"\n{'='*50}")
    print(f"📊 第 {cycle_num} 轮交易")
    print(f"{'='*50}")
    
    # 1. 获取实时价格
    prices = get_realtime_prices()
    print(f"\n📈 实时行情:")
    for code, data in prices.items():
        print(f"   {code}: ¥{data['price']:.2f} ({data['change_pct']:+.2f}%) [{data['source']}]")
    
    # 2. 生成信号
    signals = generate_factor_signals(prices, portfolio)
    print(f"\n📡 信号分析:")
    for code, sig in signals.items():
        emoji = "🟢" if sig['decision'] == '买入' else "🔴" if sig['decision'] == '卖出' else "⚪"
        print(f"   {emoji} {code}: {sig['decision']} (置信度{sig['confidence']}%) - {sig['reason']}")
    
    # 3. 执行交易
    print(f"\n💰 交易执行:")
    trades = 0
    for code, sig in signals.items():
        if sig['decision'] == '持有':
            continue
        
        if code not in prices:
            continue
        
        price = prices[code]['price']
        
        # 风控检查
        ok, msg = check_risk_control(portfolio, sig['decision'], code, price, signals)
        if not ok:
            print(f"   ⏭️ {code}: 风控拦截 - {msg}")
            continue
        
        # 执行交易
        if sig['decision'] == '买入':
            # 买100股
            ok, msg = portfolio.buy(code, price, 100)
            if ok:
                print(f"   ✅ 买入 {code}: 100股 @ ¥{price}")
                trades += 1
            else:
                print(f"   ❌ 买入失败: {msg}")
        
        elif sig['decision'] == '卖出':
            ok, msg = portfolio.sell(code, price)
            if ok:
                print(f"   ✅ 卖出 {code} @ ¥{price}")
                trades += 1
            else:
                print(f"   ❌ 卖出失败: {msg}")
    
    # 4. 持仓状态
    print(f"\n📋 持仓状态:")
    total_value = portfolio.cash
    for code, pos in portfolio.positions.items():
        if code in prices:
            current_price = prices[code]['price']
            value = pos['shares'] * current_price
            profit = (current_price - pos['avg_cost']) / pos['avg_cost'] * 100
            total_value += value
            print(f"   {code}: {pos['shares']}股 @ 成本{pos['avg_cost']:.2f}/现{current_price:.2f} ({profit:+.2f}%)")
    
    print(f"\n💵 现金: ¥{portfolio.cash:.2f} | 总资产: ¥{total_value:.2f}")
    
    return trades


def main():
    """主函数"""
    print("="*60)
    print("🚀 A股量化交易系统 v3.0 - 因子驱动版")
    print("="*60)
    print(f"监控股票: {WATCH_LIST}")
    print(f"启动时间: {datetime.now()}")
    
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
