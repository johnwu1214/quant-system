#!/usr/bin/env python3
# -*- coding: utf-8模拟交易测试系统 -*-
"""
A股盘中 v2.0
持续交易 + 真实价格模拟(带波动) + 基础风控
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import json
import os
import random
from datetime import datetime, time
import time as time_module

# 基础价格 (从东方财富获取的真实价格 2026-03-04)
BASE_PRICES = {
    '603960': 25.72,  # 克莱机电
    '600938': 42.00,  # 中国海油
    '600329': 41.20,  # 达仁堂 (待确认)
    '002737': 22.80,  # 葵花药业
}

# 尝试获取真实价格
def get_realtime_prices():
    """获取实时价格 - tushare优先,备用模拟"""
    prices = BASE_PRICES.copy()
    
    try:
        import tushare as ts
        codes = list(prices.keys())
        df = ts.get_realtime_quotes(codes)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = row['code']
                if code in prices:
                    prices[code] = round(float(row['price']), 2)
            print(f"📡 tushare 实时行情")
            return prices
    except Exception as e:
        print(f"tushare获取失败: {e}")
    
    # 备用: 使用带波动的模拟价格
    for code in prices:
        change = random.uniform(-0.01, 0.01)  # 减小波动
        prices[code] = round(prices[code] * (1 + change), 2)
    print(f"🎲 使用模拟行情(波动±1%)")
    
    return prices

def generate_signals(prices, portfolio):
    """生成交易信号 - 改进版"""
    signals = {}
    
    for code, price in prices.items():
        # 基于简单技术指标逻辑
        # 1. 计算历史均价(模拟)
        base_price = BASE_PRICES.get(code, price)
        
        # 2. 信号逻辑 - 调整阈值使其更活跃
        change_pct = (price - base_price) / base_price * 100
        
        # 加入更多随机因素使交易更活跃
        random_factor = random.uniform(0, 100)
        
        if change_pct < -2 or random_factor < 15:
            # 超跌反弹 或 随机买入 - 买入
            signals[code] = {'decision': '买入', 'confidence': 70 + random.randint(0, 25), 'reason': '超跌/随机'}
        elif change_pct > 3 or (random_factor > 85 and code in portfolio.positions):
            # 涨幅盈利 或 随机卖出(持仓时) - 卖出
            signals[code] = {'decision': '卖出', 'confidence': 70 + random.randint(0, 25), 'reason': '涨幅/随机'}
        elif change_pct < 0:
            # 下跌 - 持有/加仓
            signals[code] = {'decision': '持有', 'confidence': 50 + random.randint(0, 30), 'reason': '小幅下跌'}
        else:
            # 正常 - 持有
            signals[code] = {'decision': '持有', 'confidence': 45 + random.randint(0, 35), 'reason': '正常波动'}
        
        # 检查是否持仓
        if code in portfolio.positions:
            # 持仓股如果有盈利考虑卖出
            pos = portfolio.positions[code]
            pos_change = (price - pos['avg_cost']) / pos['avg_cost'] * 100
            if pos_change > 5:
                signals[code] = {'decision': '卖出', 'confidence': 80 + random.randint(0, 15), 'reason': '止盈'}
            elif pos_change < -3:
                signals[code] = {'decision': '持有', 'confidence': 60, 'reason': '浮亏持有'}
    
    return signals

def check_risk_control(portfolio, action, code, price):
    """风控检查"""
    # 1. 检查持仓上限
    if action == '买入':
        if len(portfolio.positions) >= 4:
            return False, "持仓上限4只"
    
    # 2. 检查单股仓位
    if action == '买入' and code in portfolio.positions:
        pos_value = portfolio.positions[code]['shares'] * price
        total_value = portfolio.cash + sum(p['shares'] * BASE_PRICES.get(pcode, p['avg_cost']) for pcode, p in portfolio.positions.items())
        if pos_value / total_value > 0.4:
            return False, "单股仓位超40%"
    
    # 3. 检查现金余额
    if action == '买入':
        required = price * 100  # 最小买入单位
        if portfolio.cash < required:
            return False, "现金不足"
    
    return True, "通过"

def run_trading_round():
    """执行一轮交易"""
    from simulated_trading import SimulatedPortfolio, StrategyTester
    
    portfolio_file = '/Users/john.wu/quant_system/test_20260304.json'
    
    # 加载组合
    if os.path.exists(portfolio_file):
        p = SimulatedPortfolio()
        p.load(portfolio_file)
    else:
        p = SimulatedPortfolio(100000, "小龙虾测试组合")
        # 初始建仓
        p.buy('603960', '克莱机电', BASE_PRICES['603960'], 2000)
        p.buy('600329', '达仁堂', BASE_PRICES['600329'], 1000)
        p.save(portfolio_file)
    
    # 获取价格
    prices = get_realtime_prices()
    
    # 生成信号
    signals = generate_signals(prices, p)
    
    # 执行交易(带风控)
    actions_taken = []
    for code, signal in signals.items():
        decision = signal.get('decision', '')
        confidence = signal.get('confidence', 0)
        
        # 风控检查
        if '买入' in decision and confidence >= 70:
            ok, reason = check_risk_control(p, '买入', code, prices[code])
            if not ok:
                actions_taken.append(f"❌ {code} 买入被风控拦截: {reason}")
                continue
            if code not in p.positions:
                success = p.buy(code, code, prices[code])
                if success:
                    actions_taken.append(f"✅ 买入 {code} @ ¥{prices[code]}")
        
        elif '卖出' in decision and code in p.positions:
            ok, reason = check_risk_control(p, '卖出', code, prices[code])
            if not ok:
                actions_taken.append(f"❌ {code} 卖出被风控拦截: {reason}")
                continue
            success = p.sell(code, prices[code])
            if success:
                pos = p.positions.get(code, {'name': code})
                actions_taken.append(f"✅ 卖出 {code} @ ¥{prices[code]}")
    
    # 更新权益
    p.update_equity(prices)
    p.save(portfolio_file)
    
    # 记录日志
    log_entry = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'prices': prices,
        'signals': signals,
        'actions': actions_taken,
        'portfolio_value': p.get_portfolio_value(prices),
        'cash': p.cash,
        'positions_count': len(p.positions)
    }
    
    log_file = '/Users/john.wu/quant_system/test_log_20260304.json'
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    logs.append(log_entry)
    with open(log_file, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    
    return log_entry, p

def is_trading_time():
    """检查是否在交易时间"""
    now = datetime.now()
    current_time = now.time()
    
    # 上午: 9:30-11:30
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    
    # 下午: 13:00-15:00
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    
    # 周末
    if now.weekday() >= 5:
        return False
    
    if morning_start <= current_time <= morning_end:
        return True
    if afternoon_start <= current_time <= afternoon_end:
        return True
    
    return False

def get_next_interval():
    """计算下次执行间隔(秒)"""
    now = datetime.now()
    current_time = now.time()
    
    # 交易时间内: 5分钟执行一次
    if now.weekday() < 5:
        if time(9, 25) <= current_time < time(11, 35):
            return 300  # 5分钟
        if time(12, 55) <= current_time < time(15, 5):
            return 300  # 5分钟
    
    # 非交易时间: 检查是否快开盘
    if time(9, 0) <= current_time < time(9, 30):
        return (datetime.now().replace(hour=9, minute=25, second=0) - now).seconds
    if time(11, 30) <= current_time < time(13, 0):
        return (datetime.now().replace(hour=12, minute=55, second=0) - now).seconds
    if time(15, 0) <= current_time < time(15, 5):
        return (datetime.now().replace(hour=15, minute=0, second=0) - now).seconds + 86400  # 下一天
    
    # 其他时间: 等待1小时
    return 3600

if __name__ == "__main__":
    print("🚀 A股盘中模拟交易系统 v2.0 启动")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 立即执行一轮
    log_entry, portfolio = run_trading_round()
    
    print(f"\n⏰ {log_entry['time']}")
    print(f"📊 价格: {log_entry['prices']}")
    print(f"🔧 动作: {log_entry['actions']}")
    print(f"💰 组合价值: ¥{log_entry['portfolio_value']:,.0f}")
    print(f"📦 持仓: {log_entry['positions_count']}只, 现金: ¥{log_entry['cash']:,.0f}")
