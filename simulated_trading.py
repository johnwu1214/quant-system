#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟交易系统
验证策略有效性，积累业绩记录
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import json
import os


class SimulatedPortfolio:
    """模拟组合"""
    
    def __init__(self, initial_capital: float = 100000, name: str = "默认组合"):
        self.name = name
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {code: {'shares': x, 'avg_cost': y}}
        self.trades = []  # 交易记录
        self.equity_curve = []  # 权益曲线
        self.start_date = datetime.now().strftime('%Y-%m-%d')
        
        # 交易统计
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_return': 0,
            'max_drawdown': 0,
        }
    
    def buy(self, code: str, name: str, price: float, shares: int = 100) -> bool:
        """买入"""
        cost = price * shares
        if cost > self.cash:
            return False
        
        self.cash -= cost
        
        if code in self.positions:
            # 加仓
            old_shares = self.positions[code]['shares']
            old_cost = self.positions[code]['avg_cost'] * old_shares
            new_shares = old_shares + shares
            new_cost = (old_cost + cost) / new_shares
            self.positions[code] = {'shares': new_shares, 'avg_cost': new_cost, 'name': name}
        else:
            self.positions[code] = {'shares': shares, 'avg_cost': price, 'name': name}
        
        self.trades.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'code': code,
            'name': name,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'amount': cost
        })
        
        self.stats['total_trades'] += 1
        return True
    
    def sell(self, code: str, price: float, shares: int = None) -> bool:
        """卖出"""
        if code not in self.positions:
            return False
        
        pos = self.positions[code]
        sell_shares = shares or pos['shares']
        
        if sell_shares > pos['shares']:
            sell_shares = pos['shares']
        
        revenue = price * sell_shares
        self.cash += revenue
        
        # 更新持仓
        remaining = pos['shares'] - sell_shares
        if remaining > 0:
            self.positions[code]['shares'] = remaining
        else:
            del self.positions[code]
        
        # 记录交易
        cost = pos['avg_cost'] * sell_shares
        profit = revenue - cost
        is_win = profit > 0
        
        self.trades.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'code': code,
            'name': pos['name'],
            'action': 'SELL',
            'price': price,
            'shares': sell_shares,
            'amount': revenue,
            'profit': profit,
            'return_pct': profit / cost * 100 if cost > 0 else 0
        })
        
        if is_win:
            self.stats['winning_trades'] += 1
        else:
            self.stats['losing_trades'] += 1
        
        return True
    
    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """组合市值"""
        position_value = 0
        for code, pos in self.positions.items():
            price = prices.get(code, pos['avg_cost'])
            position_value += price * pos['shares']
        return self.cash + position_value
    
    def get_positions(self) -> List[Dict]:
        """持仓明细"""
        result = []
        for code, pos in self.positions.items():
            result.append({
                'code': code,
                'name': pos['name'],
                'shares': pos['shares'],
                'avg_cost': pos['avg_cost']
            })
        return result
    
    def update_equity(self, prices: Dict[str, float]):
        """更新权益曲线"""
        total_value = self.get_portfolio_value(prices)
        self.equity_curve.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'value': total_value,
            'return_pct': (total_value - self.initial_capital) / self.initial_capital * 100
        })
    
    def get_stats(self) -> Dict:
        """统计"""
        total_value = self.cash + sum(
            p['shares'] * p['avg_cost'] for p in self.positions.values()
        )
        
        total_return = total_value - self.initial_capital
        return_pct = total_return / self.initial_capital * 100
        
        win_rate = 0
        if self.stats['winning_trades'] + self.stats['losing_trades'] > 0:
            win_rate = self.stats['winning_trades'] / (
                self.stats['winning_trades'] + self.stats['losing_trades']
            ) * 100
        
        return {
            'name': self.name,
            'initial_capital': self.initial_capital,
            'current_value': total_value,
            'total_return': total_return,
            'return_pct': return_pct,
            'cash': self.cash,
            'position_count': len(self.positions),
            'total_trades': self.stats['total_trades'],
            'winning_trades': self.stats['winning_trades'],
            'losing_trades': self.stats['losing_trades'],
            'win_rate': win_rate,
            'start_date': self.start_date
        }
    
    def save(self, filepath: str):
        """保存记录"""
        data = {
            'name': self.name,
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'positions': self.positions,
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'stats': self.stats
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self, filepath: str):
        """加载记录"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.name = data['name']
        self.initial_capital = data['initial_capital']
        self.cash = data['cash']
        self.positions = data['positions']
        self.trades = data['trades']
        self.equity_curve = data['equity_curve']
        self.stats = data['stats']


class StrategyTester:
    """策略测试器"""
    
    def __init__(self, portfolio: SimulatedPortfolio):
        self.portfolio = portfolio
    
    def run_signal_based_test(self, signals: Dict[str, Dict], prices: Dict[str, float]) -> Dict:
        """
        基于信号的自动测试
        
        signals: {code: {'decision': '买入'/'卖出'/'持有', 'confidence': xx}}
        prices: {code: current_price}
        """
        results = []
        
        for code, signal in signals.items():
            decision = signal.get('decision', '')
            confidence = signal.get('confidence', 0)
            price = prices.get(code, 0)
            
            # 买入信号 且 置信度高 且 有钱
            if '买入' in decision and confidence >= 70:
                if code not in self.portfolio.positions:
                    success = self.portfolio.buy(code, signal.get('name', code), price)
                    if success:
                        results.append(f"买入 {code} @ ¥{price}")
            
            # 卖出信号 且 持仓中
            elif '卖出' in decision and code in self.portfolio.positions:
                success = self.portfolio.sell(code, price)
                if success:
                    results.append(f"卖出 {code} @ ¥{price}")
        
        return {
            'actions': results,
            'portfolio_value': self.portfolio.get_portfolio_value(prices)
        }


def create_demo_portfolio() -> SimulatedPortfolio:
    """创建演示组合"""
    p = SimulatedPortfolio(100000, "小龙虾模拟组合")
    
    # 初始买入一些
    p.buy('603960', '克莱机电', 17.41, 1500)
    p.buy('600938', '中国海油', 18.51, 300)
    
    return p


if __name__ == "__main__":
    # 测试
    p = create_demo_portfolio()
    print("✅ 模拟交易系统已创建")
    print(f"初始资金: ¥{p.initial_capital:,.0f}")
    print(f"起始日期: {p.start_date}")
