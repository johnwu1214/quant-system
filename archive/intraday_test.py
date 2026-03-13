#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股盘中模拟交易测试 - 2026年3月4日
自动获取信号、执行交易、记录数据
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import json
import os
from datetime import datetime, time
import pandas as pd

# 尝试导入数据模块
try:
    from akshare_data import get_realtime_quotes
    DATA_SOURCE = 'akshare'
except:
    try:
        from multi_source_data import get_realtime_data
        DATA_SOURCE = 'multi_source'
    except:
        DATA_SOURCE = 'mock'

def get_current_prices():
    """获取当前价格"""
    codes = ['603960', '600938', '600329', '002737']  # 持仓股票
    
    if DATA_SOURCE == 'akshare':
        try:
            df = get_realtime_quotes(codes)
            if df is not None and len(df) > 0:
                return {row['代码']: float(row['最新价']) for _, row in df.iterrows()}
        except Exception as e:
            print(f"akshare获取失败: {e}")
    
    # 备用: 使用模拟数据
    return {
        '603960': 17.41,  # 克莱机电
        '600938': 18.51,  # 中国海油
        '600329': 25.30,  # 达仁堂
        '002737': 22.80,  # 葵花药业
    }

def generate_signals(prices):
    """生成交易信号 - 基于简单技术指标"""
    signals = {}
    
    # 这里使用简化的信号生成逻辑
    # 实际应该调用 ai_strategy_generator
    
    for code, price in prices.items():
        # 模拟信号: 随机生成买入/卖出/持有
        import random
        r = random.random()
        
        if r < 0.1:
            signals[code] = {'decision': '卖出', 'confidence': 70 + random.randint(0, 25)}
        elif r < 0.2:
            signals[code] = {'decision': '买入', 'confidence': 60 + random.randint(0, 30)}
        else:
            signals[code] = {'decision': '持有', 'confidence': 50 + random.randint(0, 40)}
    
    return signals

def run_trading_round():
    """执行一轮交易"""
    from simulated_trading import SimulatedPortfolio
    
    # 加载组合
    portfolio_file = '/Users/john.wu/quant_system/test_20260304.json'
    if os.path.exists(portfolio_file):
        p = SimulatedPortfolio()
        p.load(portfolio_file)
    else:
        p = SimulatedPortfolio(100000, "小龙虾测试组合")
    
    # 获取价格
    prices = get_current_prices()
    
    # 生成信号
    signals = generate_signals(prices)
    
    # 执行交易
    from simulated_trading import StrategyTester
    tester = StrategyTester(p)
    result = tester.run_signal_based_test(signals, prices)
    
    # 更新权益
    p.update_equity(prices)
    
    # 保存状态
    p.save(portfolio_file)
    
    # 记录日志
    log_entry = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'prices': prices,
        'signals': signals,
        'actions': result['actions'],
        'portfolio_value': result['portfolio_value']
    }
    
    # 追加到日志
    log_file = '/Users/john.wu/quant_system/test_log_20260304.json'
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    logs.append(log_entry)
    with open(log_file, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    
    # 输出
    print(f"\n{'='*50}")
    print(f"⏰ 交易轮次 - {log_entry['time']}")
    print(f"{'='*50}")
    print(f"📊 当前价格: {prices}")
    print(f"📈 信号: {signals}")
    print(f"🔧 动作: {result['actions']}")
    print(f"💰 组合价值: ¥{result['portfolio_value']:,.2f}")
    
    # 持仓状态
    positions = p.get_positions()
    print(f"📦 持仓: {len(positions)} 只")
    for pos in positions:
        current = prices.get(pos['code'], pos['avg_cost'])
        pnl = (current - pos['avg_cost']) / pos['avg_cost'] * 100
        print(f"   {pos['code']} {pos['name']}: {pos['shares']}股, 成本¥{pos['avg_cost']:.2f}, 当前¥{current:.2f}, 浮动{pnl:+.2f}%")
    
    return log_entry

if __name__ == "__main__":
    print("🚀 A股盘中模拟交易测试")
    run_trading_round()
